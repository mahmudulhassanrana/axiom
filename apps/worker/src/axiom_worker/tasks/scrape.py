from __future__ import annotations

import logging
import random
import time
import uuid
from typing import Any
from uuid import UUID

import requests
from axiom_compliance import ComplianceSettings, ScrapeComplianceContext
from axiom_compliance.exceptions import ComplianceError, RobotsTxtDisallowedError
from axiom_compliance.lists import hostname_for_url
from axiom_extractors import HtmlExtractor, PlaywrightExtractor, extract_for_crawl_engine
from axiom_extractors.assets import enrich_payload_with_assets
from axiom_extractors.entities import extract_structured_entities
from celery import Task
from playwright.sync_api import Error as PlaywrightError

from axiom_worker.celery_app import app
from axiom_worker.compliance_fetch import run_compliance_before_fetch
from axiom_worker.crawl_runner import run_multi_page_scrape
from axiom_worker.extracted_persistence import insert_extracted_data
from axiom_worker.job_events import publish_job_event
from axiom_worker.job_status import (
    claim_run_for_scrape,
    load_completed_scrape_document,
    mark_failed,
    mark_restricted,
    mark_succeeded,
)
from axiom_worker.scrape_audit import record_scrape_audit_event_sync
from axiom_worker.sitemap_urls import default_sitemap_url_for_base, resolve_sitemap_seed_urls

logger = logging.getLogger(__name__)


def _pre_fetch_jitter(max_sec: float | None) -> None:
    if max_sec is None or max_sec <= 0:
        return
    time.sleep(random.uniform(0.0, min(2.0, float(max_sec))))


_html_extractor = HtmlExtractor()
_playwright_extractor = PlaywrightExtractor()

_RETRYABLE_HTTP = frozenset({429, 500, 502, 503, 504})


def _select_extractors(settings: ComplianceSettings) -> tuple[HtmlExtractor, PlaywrightExtractor]:
    if not settings.enabled:
        return _html_extractor, _playwright_extractor
    ua = settings.user_agent
    return (
        HtmlExtractor(headers={"User-Agent": ua}),
        PlaywrightExtractor(user_agent=ua),
    )


def _job_audit_extra(
    job_id: str | None,
    run_id: str | None,
    schedule_id: str | None = None,
) -> dict[str, str] | None:
    if not job_id and not run_id and not schedule_id:
        return None
    out: dict[str, str] = {}
    if job_id:
        out["job_id"] = job_id
    if run_id:
        out["run_id"] = run_id
    if schedule_id:
        out["schedule_id"] = schedule_id
    return out


def _max_retries_cap(self: Task) -> int:
    raw = self.request.kwargs.get("max_retries_override")
    if raw is None:
        return 3
    try:
        return max(0, min(int(raw), 50))
    except (TypeError, ValueError):
        return 3


class ScrapePipelineTask(Task):
    """Ensure DB reflects failure after Celery gives up on retries."""

    def on_failure(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo) -> None:
        job_id = kwargs.get("job_id")
        run_id = kwargs.get("run_id")
        if not job_id or not run_id:
            return
        try:
            mark_failed(UUID(str(run_id)), UUID(str(job_id)), str(exc))
        except Exception:
            logger.exception(
                "scrape_task.on_failure_mark_failed_failed",
                extra={"job_id": str(job_id), "run_id": str(run_id)},
            )


@app.task(
    bind=True,
    base=ScrapePipelineTask,
    name="axiom.scrape",
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def scrape_task(
    self: Task,
    *,
    url: str,
    engine: str = "html_requests",
    include_html: bool = False,
    user_id: str | None = None,
    organization_id: str | None = None,
    audit_correlation_id: str | None = None,
    compliance_preverified: bool = False,
    job_id: str | None = None,
    run_id: str | None = None,
    schedule_id: str | None = None,
    max_retries_override: int | None = None,
    crawl_max_pages: int | None = None,
    crawl_delay_seconds: float | None = None,
    crawl_jitter_seconds: float | None = None,
    crawl_allow_external: bool | None = None,
    crawl_max_external_pages: int | None = None,
    crawl_max_external_per_host: int | None = None,
    pre_fetch_jitter_max_seconds: float | None = None,
    robots_override: bool = False,
    **forward_kw: Any,
) -> dict[str, Any]:
    """
    Fetch ``url`` and return a normalized extraction payload (JSON-serializable dict).

    Retries with exponential backoff + jitter for transient HTTP, network, and browser errors.

    ``**forward_kw`` absorbs ``crawl_type``, ``sitemap_url``, and future API fields so Celery
    never raises "unexpected keyword argument" after API/worker version skew.
    """
    crawl_type = forward_kw.pop("crawl_type", None)
    sitemap_url = forward_kw.pop("sitemap_url", None)
    if forward_kw:
        logger.warning(
            "scrape_task.unused_forward_kwargs",
            extra={"keys": list(forward_kw), "celery_task_id": self.request.id},
        )

    task_id = self.request.id
    retries = self.request.retries
    settings = ComplianceSettings.from_env()
    try:
        cid = UUID(audit_correlation_id) if audit_correlation_id else uuid.uuid4()
    except ValueError:
        cid = uuid.uuid4()
    try:
        uid = UUID(user_id) if user_id else None
    except ValueError:
        uid = None
    try:
        oid = UUID(organization_id) if organization_id else None
    except ValueError:
        oid = None
    host_label = hostname_for_url(url) or "invalid"
    j_extra = _job_audit_extra(job_id, run_id, schedule_id)

    job_uuid: UUID | None = None
    run_uuid: UUID | None = None
    try:
        if job_id:
            job_uuid = UUID(job_id)
        if run_id:
            run_uuid = UUID(run_id)
    except ValueError:
        job_uuid = None
        run_uuid = None

    if retries:
        logger.warning(
            "scrape_task.retry_attempt",
            extra={
                "axiom_url": url,
                "axiom_engine": engine,
                "celery_task_id": task_id,
                "celery_retries": retries,
            },
        )
    else:
        logger.info(
            "scrape_task.start",
            extra={
                "axiom_url": url,
                "axiom_engine": engine,
                "celery_task_id": task_id,
                "include_html": include_html,
            },
        )

    logger.info(
        "Worker started scrape celery_task_id=%s job_id=%s run_id=%s url=%s",
        task_id,
        job_id,
        run_id,
        url,
    )

    ctx = ScrapeComplianceContext(
        user_id=user_id,
        organization_id=organization_id,
        audit_correlation_id=audit_correlation_id,
        celery_task_id=task_id,
        engine=engine,
        source="worker",
    )

    try:
        host_label = run_compliance_before_fetch(
            url,
            ctx=ctx,
            settings=settings,
            preverified=compliance_preverified,
            skip_robots_check=robots_override,
        )
    except ComplianceError as exc:
        record_scrape_audit_event_sync(
            correlation_id=cid,
            source="worker",
            user_id=uid,
            organization_id=oid,
            url=url,
            host=host_label,
            engine=engine,
            step="compliance",
            outcome="denied",
            error_message=str(exc),
            celery_task_id=task_id,
            extra=j_extra,
        )
        if job_uuid is not None and run_uuid is not None:
            if isinstance(exc, RobotsTxtDisallowedError):
                mark_restricted(run_uuid, job_uuid, str(exc))
                publish_job_event(
                    job_uuid,
                    {
                        "type": "job_restricted",
                        "job_id": str(job_uuid),
                        "run_id": str(run_uuid),
                        "reason": "robots_txt",
                        "detail": str(exc),
                    },
                )
                logger.warning(
                    "scrape_task.robots_restricted",
                    extra={"axiom_url": url, "celery_task_id": task_id},
                )
                return {}
            mark_failed(run_uuid, job_uuid, str(exc))
        logger.warning(
            "scrape_task.compliance_denied",
            extra={"axiom_url": url, "celery_task_id": task_id, "detail": str(exc)},
        )
        raise

    if job_uuid is not None and run_uuid is not None:
        claim = claim_run_for_scrape(run_uuid, job_uuid, celery_retries=retries)
        if claim == "completed":
            loaded = load_completed_scrape_document(run_uuid)
            if loaded is not None:
                logger.info(
                    "scrape_task.idempotent_skip_completed",
                    extra={"run_id": str(run_uuid), "celery_task_id": task_id},
                )
                return loaded
        elif claim == "failed":
            logger.info(
                "scrape_task.idempotent_skip_failed",
                extra={"run_id": str(run_uuid), "celery_task_id": task_id},
            )
            return {}
        elif claim == "already_running":
            logger.warning(
                "scrape_task.duplicate_task_skipped",
                extra={"run_id": str(run_uuid), "celery_task_id": task_id},
            )
            return {}
        elif claim == "restricted":
            logger.info(
                "scrape_task.skip_restricted",
                extra={"run_id": str(run_uuid), "celery_task_id": task_id},
            )
            return {}

    html_ex, pw_ex = _select_extractors(settings)

    crawl_n = int(crawl_max_pages if crawl_max_pages is not None else 1)
    crawl_n = max(1, min(50, crawl_n))
    c_delay = float(crawl_delay_seconds if crawl_delay_seconds is not None else 1.5)
    c_jitter = float(crawl_jitter_seconds if crawl_jitter_seconds is not None else 0.5)
    allow_ext = bool(crawl_allow_external) if crawl_allow_external is not None else False
    ext_total = int(crawl_max_external_pages if crawl_max_external_pages is not None else 25)
    ext_total = max(0, min(50, ext_total))
    ext_per_host = int(crawl_max_external_per_host if crawl_max_external_per_host is not None else 5)
    ext_per_host = max(1, min(20, ext_per_host))
    pre_jitter = float(pre_fetch_jitter_max_seconds if pre_fetch_jitter_max_seconds is not None else 0.0)

    ct = str(crawl_type or "single_page").strip().lower()
    if ct == "multi_page":
        crawl_n = max(2, crawl_n)
    use_sitemap_mode = ct == "sitemap"
    # Persisted jobs use crawl_runner so list pages can enqueue member/profile detail URLs.
    use_multi = job_uuid is not None and run_uuid is not None

    if use_multi:
        seed_urls: list[str] | None = None
        expand_links = True
        if use_sitemap_mode:
            expand_links = False
            sm = (str(sitemap_url).strip() if sitemap_url else "") or default_sitemap_url_for_base(url)
            try:
                seed_urls = resolve_sitemap_seed_urls(sm, crawl_n)
            except Exception as exc:
                if job_uuid is not None and run_uuid is not None:
                    mark_failed(run_uuid, job_uuid, f"Sitemap resolution failed: {exc}")
                raise
            if not seed_urls:
                msg = "Sitemap produced no URLs"
                mark_failed(run_uuid, job_uuid, msg)
                return {}
        try:
            out = run_multi_page_scrape(
                seed_url=url,
                max_pages=crawl_n,
                delay_seconds=c_delay,
                jitter_seconds=c_jitter,
                engine=engine,
                html_ex=html_ex,
                pw_ex=pw_ex,
                settings=settings,
                user_id=user_id,
                organization_id=organization_id,
                audit_correlation_id=audit_correlation_id,
                celery_task_id=task_id,
                job_id=job_uuid,
                run_id=run_uuid,
                compliance_preverified=compliance_preverified,
                allow_external=allow_ext,
                max_external_total=ext_total,
                max_external_per_host=ext_per_host,
                pre_fetch_jitter_max_seconds=pre_jitter,
                seed_urls=seed_urls,
                expand_links=expand_links,
                robots_override=robots_override,
            )
        except ComplianceError as exc:
            if isinstance(exc, RobotsTxtDisallowedError):
                mark_restricted(run_uuid, job_uuid, str(exc))
                publish_job_event(
                    job_uuid,
                    {
                        "type": "job_restricted",
                        "job_id": str(job_uuid),
                        "run_id": str(run_uuid),
                        "reason": "robots_txt",
                        "detail": str(exc),
                    },
                )
                return {}
            mark_failed(run_uuid, job_uuid, str(exc))
            raise
        except Exception as exc:
            mark_failed(run_uuid, job_uuid, str(exc))
            raise
        if out["pages_done"] == 0:
            msg = "Crawl produced no extractable pages"
            mark_failed(run_uuid, job_uuid, msg)
            return {}
        mark_succeeded(
            run_uuid,
            job_uuid,
            {
                "http_status": None,
                "extractor_kind": engine,
                "celery_task_id": task_id,
                "pages_scraped": out["pages_done"],
                "crawl_max_pages": crawl_n,
            },
        )
        return out.get("last_payload") or {}

    if job_uuid is not None and run_uuid is not None:
        publish_job_event(
            job_uuid,
            {
                "type": "job_started",
                "job_id": str(job_uuid),
                "run_id": str(run_uuid),
                "max_pages": 1,
                "seed_url": url,
            },
        )

    logger.info("Scraping started url=%s engine=%s", url, engine)
    _pre_fetch_jitter(pre_jitter)
    try:
        if engine not in ("html_requests", "playwright"):
            raise ValueError(f"Unsupported engine: {engine!r}")
        doc, extraction_type = extract_for_crawl_engine(
            url=url,
            include_html=include_html,
            engine=engine,  # type: ignore[arg-type]
            html_ex=html_ex,
            pw_ex=pw_ex,
        )
    except ValueError as exc:
        logger.exception(
            "scrape_task.failed_no_retry",
            extra={"axiom_url": url, "celery_task_id": task_id, "axiom_engine": engine},
        )
        record_scrape_audit_event_sync(
            correlation_id=cid,
            source="worker",
            user_id=uid,
            organization_id=oid,
            url=url,
            host=host_label,
            engine=engine,
            step="fetch",
            outcome="error",
            error_message=str(exc),
            celery_task_id=task_id,
            extra=j_extra,
        )
        if job_uuid is not None and run_uuid is not None:
            mark_failed(run_uuid, job_uuid, str(exc))
        raise
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status in _RETRYABLE_HTTP or status is None:
            logger.warning(
                "scrape_task.transient_http_error",
                extra={
                    "axiom_url": url,
                    "celery_task_id": task_id,
                    "http_status": status,
                },
                exc_info=exc,
            )
            raise self.retry(exc=exc, max_retries=_max_retries_cap(self)) from exc
        logger.warning(
            "scrape_task.client_http_error",
            extra={
                "axiom_url": url,
                "celery_task_id": task_id,
                "http_status": status,
            },
        )
        record_scrape_audit_event_sync(
            correlation_id=cid,
            source="worker",
            user_id=uid,
            organization_id=oid,
            url=url,
            host=host_label,
            engine=engine,
            step="fetch",
            outcome="error",
            error_message=str(exc),
            http_status=status,
            celery_task_id=task_id,
            extra=j_extra,
        )
        if job_uuid is not None and run_uuid is not None:
            mark_failed(run_uuid, job_uuid, str(exc))
        raise
    except (requests.Timeout, requests.ConnectionError) as exc:
        logger.warning(
            "scrape_task.transient_network_error",
            extra={"axiom_url": url, "celery_task_id": task_id},
            exc_info=exc,
        )
        raise self.retry(exc=exc, max_retries=_max_retries_cap(self)) from exc
    except PlaywrightError as exc:
        logger.warning(
            "scrape_task.transient_playwright_error",
            extra={"axiom_url": url, "celery_task_id": task_id},
            exc_info=exc,
        )
        raise self.retry(exc=exc, max_retries=_max_retries_cap(self)) from exc
    except requests.RequestException as exc:
        logger.warning(
            "scrape_task.transient_request_error",
            extra={"axiom_url": url, "celery_task_id": task_id},
            exc_info=exc,
        )
        raise self.retry(exc=exc, max_retries=_max_retries_cap(self)) from exc

    text_body = (doc.text or "").strip()
    if not text_body:
        empty_msg = "Empty or whitespace-only extracted text"
        record_scrape_audit_event_sync(
            correlation_id=cid,
            source="worker",
            user_id=uid,
            organization_id=oid,
            url=url,
            host=host_label,
            engine=engine,
            step="normalize",
            outcome="error",
            error_message=empty_msg,
            http_status=doc.http_status,
            celery_task_id=task_id,
            extra=j_extra,
        )
        if job_uuid is not None and run_uuid is not None:
            mark_failed(run_uuid, job_uuid, empty_msg)
        logger.warning(
            "scrape_task.empty_text",
            extra={"axiom_url": url, "celery_task_id": task_id},
        )
        return doc.to_json_dict()

    record_scrape_audit_event_sync(
        correlation_id=cid,
        source="worker",
        user_id=uid,
        organization_id=oid,
        url=url,
        host=host_label,
        engine=engine,
        step="fetch",
        outcome="success",
        http_status=doc.http_status,
        celery_task_id=task_id,
        extra=j_extra,
    )

    logger.info(
        "Scraping success url=%s http_status=%s text_len=%s",
        url,
        doc.http_status,
        len((doc.text or "").strip()),
    )

    links_dump = [link.model_dump(mode="json") for link in doc.links]
    imgs, file_links = enrich_payload_with_assets(
        page_url=url,
        html=doc.html,
        links=links_dump,
    )
    structured = extract_structured_entities(html=doc.html, text=doc.text)
    payload = doc.to_json_dict()
    plm = payload.setdefault("metadata", {})
    if isinstance(plm, dict):
        plm.setdefault("crawl_source", "internal")
        plm.setdefault("crawl_seed_url", url)
    payload["page_url"] = url
    payload["images"] = imgs
    payload["files"] = file_links
    payload["file_links"] = file_links
    payload["structured_entities"] = structured
    payload["extraction_type"] = extraction_type
    if job_uuid is not None and run_uuid is not None:
        publish_job_event(
            job_uuid,
            {
                "type": "page_scraped",
                "url": url,
                "pages_done": 1,
                "max_pages": 1,
                "title": doc.title,
            },
        )
        logger.info(
            "scrape_task.persist_start",
            extra={"axiom_url": url, "run_id": str(run_uuid), "celery_task_id": task_id},
        )
        try:
            insert_extracted_data(run_uuid, payload)
        except Exception as persist_exc:
            logger.exception(
                "scrape_task.persist_failed",
                extra={"axiom_url": url, "run_id": str(run_uuid), "celery_task_id": task_id},
            )
            mark_failed(run_uuid, job_uuid, f"Failed to save extracted data: {persist_exc}")
            raise
        mark_succeeded(
            run_uuid,
            job_uuid,
            {
                "http_status": doc.http_status,
                "extractor_kind": doc.extractor_kind,
                "celery_task_id": task_id,
                "pages_scraped": 1,
            },
        )
        publish_job_event(
            job_uuid,
            {
                "type": "job_completed",
                "job_id": str(job_uuid),
                "run_id": str(run_uuid),
                "pages_done": 1,
                "status": "completed",
            },
        )
        logger.info(
            "scrape_task.persist_done",
            extra={"axiom_url": url, "run_id": str(run_uuid), "celery_task_id": task_id},
        )

    logger.info(
        "scrape_task.success",
        extra={
            "axiom_url": url,
            "celery_task_id": task_id,
            "axiom_engine": engine,
            "http_status": doc.http_status,
        },
    )
    return payload
