from __future__ import annotations

import logging
import os
import uuid
from typing import Any
from uuid import UUID

import requests
from axiom_compliance import (
    ComplianceSettings,
    ScrapeComplianceContext,
    run_compliance_before_fetch,
)
from axiom_compliance.exceptions import ComplianceError
from axiom_compliance.lists import hostname_for_url
from axiom_extractors import HtmlExtractor, PlaywrightExtractor
from celery import Task
from playwright.sync_api import Error as PlaywrightError

from axiom_worker.celery_app import app
from axiom_worker.extracted_persistence import insert_extracted_data
from axiom_worker.job_status import (
    claim_run_for_scrape,
    load_completed_scrape_document,
    mark_failed,
    mark_running,
    mark_succeeded,
)
from axiom_worker.scrape_audit import record_scrape_audit_event_sync

logger = logging.getLogger(__name__)

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


def _has_database_url() -> bool:
    return bool((os.environ.get("DATABASE_URL") or "").strip())


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
) -> dict[str, Any]:
    """
    Fetch ``url`` and return a normalized extraction payload (JSON-serializable dict).

    Retries with exponential backoff + jitter for transient HTTP, network, and browser errors.
    """
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
        elif not _has_database_url():
            mark_running(run_uuid, job_uuid)

    html_ex, pw_ex = _select_extractors(settings)

    try:
        if engine == "html_requests":
            doc = html_ex.extract(url, include_html=include_html)
        elif engine == "playwright":
            doc = pw_ex.extract(url, include_html=include_html)
        else:
            raise ValueError(f"Unsupported engine: {engine!r}")
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
        raise ValueError(empty_msg)

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

    payload = doc.to_json_dict()
    if job_uuid is not None and run_uuid is not None:
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
