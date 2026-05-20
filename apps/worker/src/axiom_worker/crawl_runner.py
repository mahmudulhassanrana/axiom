"""Multi-page crawl with pagination, detail pages, delay, jitter, and visited-URL tracking."""

from __future__ import annotations

import logging
import random
import time
import uuid
from collections import deque
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse
from uuid import UUID

from axiom_compliance import ComplianceSettings, ScrapeComplianceContext
from axiom_compliance.exceptions import ComplianceError
from axiom_extractors import HtmlExtractor, PlaywrightExtractor
from axiom_extractors.models import ExtractedLink
from axiom_extractors.assets import enrich_payload_with_assets
from axiom_extractors.crawl_constants import MIN_CRAWL_CHARS, MIN_CRAWL_QUALITY
from axiom_extractors.detail_links import extract_detail_links
from axiom_extractors.entities import extract_structured_entities
from axiom_extractors.human_browse import sleep_human_delay
from axiom_extractors.hybrid import extract_for_crawl_engine
from axiom_extractors.page_type import detect_page_type
from axiom_extractors.pagination_hints import sort_links_for_crawl
from axiom_extractors.pagination_nav import crawl_visit_key, extra_pagination_targets
from axiom_extractors.playwright_extractor import PlaywrightBrowserSession
from axiom_extractors.profile_record import build_profile_record

from axiom_worker.compliance_fetch import run_compliance_before_fetch
from axiom_worker.extracted_persistence import insert_extracted_data
from axiom_worker.job_events import publish_job_event

logger = logging.getLogger(__name__)


def _same_site(a: str, b: str) -> bool:
    try:
        ha = urlparse(a).hostname or ""
        hb = urlparse(b).hostname or ""
    except Exception:
        return False
    if not ha or not hb:
        return False
    return ha.lower() == hb.lower()


def _target_host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _normalize_queue_url(
    url: str,
    seed: str,
    *,
    allow_external: bool,
) -> str | None:
    url, _ = urldefrag(url.strip())
    if not url or url.startswith(("javascript:", "mailto:", "tel:", "#")):
        return None
    abs_u = urljoin(seed, url)
    if not abs_u.startswith(("http://", "https://")):
        return None
    if not allow_external and not _same_site(abs_u, seed):
        return None
    return abs_u


def _attach_crawl_fields(
    payload: dict[str, Any],
    *,
    url: str,
    page_type: str,
    crawl_session_id: str,
    parent_url: str | None,
    pages_done: int,
    max_pages: int,
    seed_url: str,
    is_external: bool,
) -> None:
    pl_meta = payload.setdefault("metadata", {})
    if isinstance(pl_meta, dict):
        pl_meta["crawl_depth"] = pages_done + 1
        pl_meta["crawl_max_pages"] = max_pages
        pl_meta["crawl_source"] = "external" if is_external else "internal"
        pl_meta.setdefault("crawl_seed_url", seed_url)
        pl_meta["page_type"] = page_type
        pl_meta["crawl_session_id"] = crawl_session_id
        if parent_url:
            pl_meta["parent_url"] = parent_url
            pl_meta["parent_list_url"] = parent_url
        if page_type == "profile":
            pl_meta["detail_page_url"] = url
    payload["page_url"] = url
    payload["page_type"] = page_type
    payload["crawl_session_id"] = crawl_session_id
    payload["parent_url"] = parent_url
    payload["detail_page_url"] = url if page_type == "profile" else None
    payload["crawl_depth"] = pages_done + 1


def run_multi_page_scrape(
    *,
    seed_url: str,
    max_pages: int,
    delay_seconds: float,
    jitter_seconds: float,
    engine: str,
    html_ex: HtmlExtractor,
    pw_ex: PlaywrightExtractor,
    settings: ComplianceSettings,
    user_id: str | None,
    organization_id: str | None,
    audit_correlation_id: str | None,
    celery_task_id: str,
    job_id: UUID,
    run_id: UUID,
    compliance_preverified: bool,
    allow_external: bool = False,
    max_external_total: int = 25,
    max_external_per_host: int = 5,
    pre_fetch_jitter_max_seconds: float = 0.0,
    seed_urls: list[str] | None = None,
    expand_links: bool = True,
    robots_override: bool = False,
) -> dict[str, Any]:
    """Scrape up to ``max_pages`` pages; persist one ``extracted_data`` row per page."""
    visited_norm: set[str] = set()
    if seed_urls:
        queue: deque[str] = deque([u for u in seed_urls if u][: max_pages * 3])
    else:
        queue = deque([seed_url])
    seed_host = _target_host(seed_url)
    pages_done = 0
    last_doc: dict[str, Any] = {}
    ext_enq_by_host: dict[str, int] = {}
    ext_enqueued_total = 0
    crawl_session_id = str(uuid.uuid4())

    pw_session: PlaywrightBrowserSession | None = None
    if engine == "playwright":
        pw_session = PlaywrightBrowserSession(pw_ex).start()

    def _is_external_page(u: str) -> bool:
        return bool(_target_host(u)) and _target_host(u) != seed_host

    def _compliance_ctx() -> ScrapeComplianceContext:
        return ScrapeComplianceContext(
            user_id=user_id,
            organization_id=organization_id,
            audit_correlation_id=audit_correlation_id,
            celery_task_id=celery_task_id,
            engine=engine,
            source="worker",
        )

    def _fetch_and_build(
        url: str,
        *,
        parent_url: str | None,
    ) -> tuple[dict[str, Any] | None, bool]:
        """Returns (payload, saved_ok). payload None if skipped."""
        try:
            doc, ext_type = extract_for_crawl_engine(
                url=url,
                include_html=True,
                engine=engine,  # type: ignore[arg-type]
                html_ex=html_ex,
                pw_ex=pw_ex,
                pw_session=pw_session,
            )
            html = doc.html or ""
        except Exception as exc:
            publish_job_event(
                job_id,
                {"type": "page_error", "url": url, "error": str(exc), "pages_done": pages_done},
            )
            if pages_done == 0 and parent_url is None:
                raise
            return None, False

        links_dump = [link.model_dump(mode="json") for link in doc.links]
        imgs, file_links = enrich_payload_with_assets(
            page_url=url,
            html=html if html else None,
            links=links_dump,
        )
        ents = extract_structured_entities(html=doc.html, text=doc.text)
        meta_in = dict(doc.metadata or {})
        page_type = detect_page_type(
            url=url,
            html=html,
            links=doc.links,
            metadata=meta_in,
        )
        if parent_url:
            page_type = "profile"

        payload = doc.to_json_dict()
        _attach_crawl_fields(
            payload,
            url=url,
            page_type=page_type,
            crawl_session_id=crawl_session_id,
            parent_url=parent_url,
            pages_done=pages_done,
            max_pages=max_pages,
            seed_url=seed_url,
            is_external=_is_external_page(url),
        )
        payload["images"] = imgs
        payload["files"] = file_links
        payload["file_links"] = file_links
        payload["structured_entities"] = ents
        payload["extraction_type"] = ext_type

        pl_meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        if page_type == "profile" and parent_url:
            profile = build_profile_record(
                detail_url=url,
                parent_url=parent_url,
                title=doc.title,
                text=doc.text,
                html=html,
                structured_entities=ents,
                images=imgs,
                links=links_dump,
            )
            existing = pl_meta.get("member_records")
            rows = [profile]
            if isinstance(existing, list):
                rows = [*existing, profile]
            pl_meta["member_records"] = rows
            payload["metadata"] = pl_meta

        text_body = (doc.text or "").strip()
        qscore = float(pl_meta.get("content_quality_score") or 0.0)
        if not text_body:
            publish_job_event(
                job_id,
                {
                    "type": "page_skipped",
                    "url": url,
                    "reason": "empty_text",
                    "pages_done": pages_done,
                },
            )
            return None, False
        if qscore < MIN_CRAWL_QUALITY and len(text_body) < MIN_CRAWL_CHARS:
            publish_job_event(
                job_id,
                {
                    "type": "page_skipped",
                    "url": url,
                    "reason": "low_content_quality",
                    "pages_done": pages_done,
                    "content_quality_score": qscore,
                },
            )
            return None, False
        return payload, True

    publish_job_event(
        job_id,
        {
            "type": "job_started",
            "job_id": str(job_id),
            "run_id": str(run_id),
            "max_pages": max_pages,
            "seed_url": seed_url,
            "allow_external": allow_external,
            "crawl_session_id": crawl_session_id,
        },
    )

    try:
        while queue and pages_done < max_pages:
            url = queue.popleft()
            vkey = crawl_visit_key(url)
            if not vkey or vkey in visited_norm:
                continue
            visited_norm.add(vkey)
            logger.info(
                "crawl.pagination_page_start",
                extra={"page_index": pages_done + 1, "max_pages": max_pages, "url": url},
            )

            try:
                run_compliance_before_fetch(
                    url,
                    ctx=_compliance_ctx(),
                    settings=settings,
                    preverified=compliance_preverified and url == seed_url,
                    skip_robots_check=robots_override,
                )
            except ComplianceError as exc:
                publish_job_event(
                    job_id,
                    {"type": "page_error", "url": url, "error": str(exc), "pages_done": pages_done},
                )
                if pages_done == 0:
                    raise
                break

            if pre_fetch_jitter_max_seconds > 0:
                time.sleep(random.uniform(0.0, min(2.0, float(pre_fetch_jitter_max_seconds))))
            sleep_human_delay(min_s=max(1.0, delay_seconds), max_s=min(4.0, delay_seconds + 2.0))

            payload, ok = _fetch_and_build(url, parent_url=None)
            if not ok or payload is None:
                continue

            html = ""
            if isinstance(payload.get("html"), str):
                html = payload["html"]
            pl_meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            page_type = str(pl_meta.get("page_type") or "unknown")

            insert_extracted_data(run_id, payload)
            pages_done += 1
            last_doc = payload

            publish_job_event(
                job_id,
                {
                    "type": "page_scraped",
                    "url": url,
                    "pages_done": pages_done,
                    "max_pages": max_pages,
                    "title": payload.get("title"),
                    "crawl_source": pl_meta.get("crawl_source"),
                    "page_type": page_type,
                },
            )
            logger.info(
                "crawl.pagination_page_saved",
                extra={"pages_done": pages_done, "max_pages": max_pages, "url": url},
            )

            list_links = payload.get("links") or []
            list_link_objs = [
                ExtractedLink(href=str(ln.get("href", "")), text=ln.get("text"))
                for ln in list_links
                if isinstance(ln, dict) and ln.get("href")
            ]
            detail_urls = extract_detail_links(
                html=html,
                page_url=url,
                seed_url=seed_url,
                links=list_link_objs,
            )
            if detail_urls:
                logger.info(
                    "crawl.detail_links_found",
                    extra={"url": url, "page_type": page_type, "count": len(detail_urls)},
                )
                for detail_url in detail_urls:
                    if pages_done >= max_pages:
                        break
                    dk = crawl_visit_key(detail_url)
                    if not dk or dk in visited_norm:
                        continue
                    logger.info(
                        "crawl.detail_page_queued",
                        extra={"list_url": url, "detail_url": detail_url},
                    )
                    try:
                        run_compliance_before_fetch(
                            detail_url,
                            ctx=_compliance_ctx(),
                            settings=settings,
                            preverified=False,
                            skip_robots_check=robots_override,
                        )
                    except ComplianceError:
                        continue
                    sleep_human_delay()
                    visited_norm.add(dk)
                    detail_payload, detail_ok = _fetch_and_build(detail_url, parent_url=url)
                    if not detail_ok or detail_payload is None:
                        continue
                    insert_extracted_data(run_id, detail_payload)
                    pages_done += 1
                    last_doc = detail_payload
                    logger.info(
                        "crawl.detail_page_scraped",
                        extra={
                            "list_url": url,
                            "detail_url": detail_url,
                            "pages_done": pages_done,
                        },
                    )
                    publish_job_event(
                        job_id,
                        {
                            "type": "page_scraped",
                            "url": detail_url,
                            "pages_done": pages_done,
                            "max_pages": max_pages,
                            "page_type": "profile",
                            "parent_url": url,
                        },
                    )
                    if pages_done >= max_pages:
                        break
                    time.sleep(
                        max(0.0, delay_seconds + random.uniform(0.0, max(0.0, jitter_seconds))),
                    )

            if pages_done >= max_pages:
                break

            if expand_links:
                doc_links = payload.get("links") or []
                link_objs = [
                    ExtractedLink(href=str(ln.get("href", "")), text=ln.get("text"))
                    for ln in doc_links
                    if isinstance(ln, dict) and ln.get("href")
                ]
                for link in sort_links_for_crawl(link_objs):
                    nxt = _normalize_queue_url(link.href, seed_url, allow_external=allow_external)
                    if not nxt:
                        continue
                    nk = crawl_visit_key(nxt)
                    if not nk or nk == crawl_visit_key(url) or nk in visited_norm:
                        continue
                    if _is_external_page(nxt):
                        if not allow_external or max_external_total <= 0:
                            continue
                        if ext_enqueued_total >= max_external_total:
                            continue
                        oh = _target_host(nxt)
                        if ext_enq_by_host.get(oh, 0) >= max_external_per_host:
                            continue
                        ext_enq_by_host[oh] = ext_enq_by_host.get(oh, 0) + 1
                        ext_enqueued_total += 1
                    logger.info(
                        "crawl.pagination_next_enqueued",
                        extra={"from_url": url, "next_url": nxt},
                    )
                    queue.append(nxt)

                for raw_next in extra_pagination_targets(html=html, page_url=url, seed_url=seed_url):
                    nxt = _normalize_queue_url(raw_next, seed_url, allow_external=allow_external)
                    if not nxt:
                        continue
                    nk = crawl_visit_key(nxt)
                    if not nk or nk == crawl_visit_key(url) or nk in visited_norm:
                        continue
                    if _is_external_page(nxt):
                        if not allow_external or max_external_total <= 0:
                            continue
                        if ext_enqueued_total >= max_external_total:
                            continue
                        oh = _target_host(nxt)
                        if ext_enq_by_host.get(oh, 0) >= max_external_per_host:
                            continue
                        ext_enq_by_host[oh] = ext_enq_by_host.get(oh, 0) + 1
                        ext_enqueued_total += 1
                    logger.info(
                        "crawl.pagination_synthetic_next",
                        extra={"from_url": url, "next_url": nxt},
                    )
                    queue.append(nxt)

            if queue and pages_done < max_pages:
                sleep_s = max(0.0, delay_seconds + random.uniform(0.0, max(0.0, jitter_seconds)))
                time.sleep(sleep_s)

    finally:
        if pw_session is not None:
            pw_session.stop()

    publish_job_event(
        job_id,
        {
            "type": "job_completed",
            "job_id": str(job_id),
            "run_id": str(run_id),
            "pages_done": pages_done,
            "status": "completed",
        },
    )
    logger.info(
        "crawl.pagination_finished",
        extra={"pages_done": pages_done, "max_pages": max_pages, "seed_url": seed_url},
    )
    return {"last_payload": last_doc, "pages_done": pages_done}
