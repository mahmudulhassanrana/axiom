from __future__ import annotations

import asyncio
import logging
import uuid

import requests
from axiom_compliance import ComplianceSettings, ScrapeComplianceContext
from axiom_compliance.exceptions import ComplianceError
from axiom_compliance.lists import hostname_for_url
from axiom_extractors import (
    ExtractedDocument,
    HtmlExtractor,
    PlaywrightExtractor,
    extract_for_crawl_engine,
)
from axiom_extractors.entities import extract_structured_entities
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from kombu.exceptions import OperationalError
from playwright.sync_api import Error as PlaywrightError

from axiom_api.celery_client import AXIOM_QUEUE, get_celery_app
from axiom_api.core.compliance_fetch import run_compliance_before_fetch
from axiom_api.core.compliance_http import compliance_http_exception
from axiom_api.core.public_messages import client_safe_detail, format_upstream_failure
from axiom_api.db.models.user import User
from axiom_api.deps.auth import get_current_user
from axiom_api.schemas.scrape import ScrapeQueuedResponse, ScrapeRequest
from axiom_api.services.scrape_audit import record_scrape_audit_event

router = APIRouter(tags=["scrape"])
logger = logging.getLogger("axiom_api.scrape")

_html_extractor = HtmlExtractor()
_playwright_extractor = PlaywrightExtractor()


def _select_extractors(settings: ComplianceSettings) -> tuple[HtmlExtractor, PlaywrightExtractor]:
    if not settings.enabled:
        return _html_extractor, _playwright_extractor
    ua = settings.user_agent
    return (
        HtmlExtractor(headers={"User-Agent": ua}),
        PlaywrightExtractor(user_agent=ua),
    )


@router.post(
    "/scrape",
    response_model=None,
    summary="Scrape and normalize a URL",
    description=(
        "By default enqueues `axiom.scrape` on Celery (202 + task_id). "
        "Set async=false for synchronous extraction in the API. "
        "Compliance (robots.txt, domain lists, per-domain Redis rate limits, delay+jitter) "
        "runs before fetch; attempts are audit-logged (structured logs + optional DB rows)."
    ),
    responses={
        200: {"model": ExtractedDocument},
        202: {"model": ScrapeQueuedResponse},
        403: {"description": "Blocked by policy (lists or robots.txt)"},
        413: {"description": "Response body too large"},
        429: {"description": "Per-domain rate limit"},
        502: {"description": "Upstream fetch or render failed"},
        503: {"description": "Celery broker unavailable"},
        401: {"description": "Missing or invalid Bearer token / API key"},
    },
)
async def scrape(
    payload: ScrapeRequest,
    _user: User = Depends(get_current_user),
) -> ExtractedDocument | JSONResponse:
    url_str = str(payload.url)
    settings = ComplianceSettings.from_env()
    correlation_id = uuid.uuid4()
    ctx = ScrapeComplianceContext(
        user_id=str(_user.id),
        organization_id=str(_user.organization_id),
        audit_correlation_id=str(correlation_id),
        engine=payload.engine,
        source="api",
    )

    try:
        host = await asyncio.to_thread(
            run_compliance_before_fetch,
            url_str,
            ctx=ctx,
            settings=settings,
            preverified=False,
            skip_robots_check=bool(payload.robots_override),
        )
    except ComplianceError as exc:
        await record_scrape_audit_event(
            correlation_id=correlation_id,
            source="api",
            user_id=_user.id,
            organization_id=_user.organization_id,
            url=url_str,
            host=hostname_for_url(url_str) or "invalid",
            engine=payload.engine,
            step="compliance",
            outcome="denied",
            error_message=str(exc),
        )
        raise compliance_http_exception(exc) from exc

    if payload.async_execution:
        celery_app = get_celery_app()
        try:
            async_result = celery_app.send_task(
                "axiom.scrape",
                kwargs={
                    "url": url_str,
                    "engine": payload.engine,
                    "include_html": payload.include_html,
                    "user_id": str(_user.id),
                    "organization_id": str(_user.organization_id),
                    "audit_correlation_id": str(correlation_id),
                    "compliance_preverified": True,
                    "crawl_max_pages": payload.crawl_max_pages,
                    "crawl_delay_seconds": payload.crawl_delay_seconds,
                    "crawl_jitter_seconds": payload.crawl_jitter_seconds,
                    "crawl_allow_external": payload.crawl_allow_external,
                    "crawl_max_external_pages": payload.crawl_max_external_pages,
                    "crawl_max_external_per_host": payload.crawl_max_external_per_host,
                    "pre_fetch_jitter_max_seconds": payload.pre_fetch_jitter_max_seconds,
                    "robots_override": bool(payload.robots_override),
                },
                queue=AXIOM_QUEUE,
            )
        except OperationalError as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=client_safe_detail(
                    code="service_unavailable",
                    production_message="The task queue is temporarily unavailable. Please try again later.",
                    developer_message=f"Celery broker unavailable: {exc}",
                ),
            ) from exc
        await record_scrape_audit_event(
            correlation_id=correlation_id,
            source="api",
            user_id=_user.id,
            organization_id=_user.organization_id,
            url=url_str,
            host=host,
            engine=payload.engine,
            step="queue",
            outcome="accepted",
            celery_task_id=async_result.id,
        )
        body = ScrapeQueuedResponse(task_id=async_result.id)
        logger.info(
            "API response sent: scrape async queued task_id=%s url=%s",
            async_result.id,
            url_str,
        )
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=body.model_dump(mode="json"),
        )

    html_ex, pw_ex = _select_extractors(settings)
    try:
        doc, ext_t = await asyncio.to_thread(
            extract_for_crawl_engine,
            url=url_str,
            include_html=payload.include_html,
            engine=payload.engine,
            html_ex=html_ex,
            pw_ex=pw_ex,
        )
        ents = extract_structured_entities(html=doc.html, text=doc.text)
        meta = dict(doc.metadata) if isinstance(doc.metadata, dict) else {}
        meta["structured_entities"] = ents
        meta["extraction_type"] = ext_t
        doc = doc.model_copy(update={"metadata": meta})
    except ValueError as exc:
        await record_scrape_audit_event(
            correlation_id=correlation_id,
            source="api",
            user_id=_user.id,
            organization_id=_user.organization_id,
            url=url_str,
            host=host,
            engine=payload.engine,
            step="fetch",
            outcome="error",
            error_message=str(exc),
        )
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=client_safe_detail(
                code="payload_too_large",
                production_message="The response exceeded configured size limits.",
                developer_message=str(exc),
            ),
        ) from exc
    except requests.HTTPError as exc:
        await record_scrape_audit_event(
            correlation_id=correlation_id,
            source="api",
            user_id=_user.id,
            organization_id=_user.organization_id,
            url=url_str,
            host=host,
            engine=payload.engine,
            step="fetch",
            outcome="error",
            error_message=str(exc),
            http_status=exc.response.status_code if exc.response is not None else None,
        )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=format_upstream_failure(exc, kind="http_error"),
        ) from exc
    except requests.RequestException as exc:
        await record_scrape_audit_event(
            correlation_id=correlation_id,
            source="api",
            user_id=_user.id,
            organization_id=_user.organization_id,
            url=url_str,
            host=host,
            engine=payload.engine,
            step="fetch",
            outcome="error",
            error_message=str(exc),
        )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=format_upstream_failure(exc, kind="request_error"),
        ) from exc
    except PlaywrightError as exc:
        await record_scrape_audit_event(
            correlation_id=correlation_id,
            source="api",
            user_id=_user.id,
            organization_id=_user.organization_id,
            url=url_str,
            host=host,
            engine=payload.engine,
            step="fetch",
            outcome="error",
            error_message=str(exc),
        )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=format_upstream_failure(exc, kind="playwright_error"),
        ) from exc

    await record_scrape_audit_event(
        correlation_id=correlation_id,
        source="api",
        user_id=_user.id,
        organization_id=_user.organization_id,
        url=url_str,
        host=host,
        engine=payload.engine,
        step="fetch",
        outcome="success",
        http_status=doc.http_status,
    )
    logger.info(
        "API response sent: scrape sync 200 url=%s http_status=%s",
        url_str,
        doc.http_status,
    )
    return doc
