from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

from axiom_compliance import ComplianceSettings, ScrapeComplianceContext
from axiom_compliance.exceptions import ComplianceError
from axiom_compliance.lists import hostname_for_url
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from axiom_api.core.compliance_fetch import run_compliance_before_fetch
from axiom_api.core.compliance_http import compliance_http_exception
from axiom_api.core.public_messages import client_safe_detail
from axiom_api.db.deps import get_db
from axiom_api.db.models.job import Job
from axiom_api.db.models.source import Source
from axiom_api.db.models.user import User
from axiom_api.deps.auth import get_current_user_bearer
from axiom_api.schemas.jobs import JobCreateRequest
from axiom_api.schemas.sources import (
    SourceCreateRequest,
    SourceDetailPublic,
    SourcePublic,
    SourceRunResponse,
    SourceUpdateRequest,
)
from axiom_api.services.job_payload_merge import build_merged_job_payload
from axiom_api.services.schedule_util import (
    cron_expression_from_source_schedule_config,
    sync_source_next_run_at,
    validate_cron_expression,
)
from axiom_api.services.scrape_audit import record_scrape_audit_event
from axiom_api.services.scrape_job_enqueue import enqueue_scrape_job

router = APIRouter(prefix="/sources", tags=["sources"])
logger = logging.getLogger("axiom_api.sources")


async def _get_source_org(session: AsyncSession, source_id: UUID, organization_id: UUID) -> Source:
    result = await session.execute(
        select(Source).where(Source.id == source_id, Source.organization_id == organization_id),
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Source not found")
    return row


def _apply_schedule_fields(source: Source) -> None:
    source.next_run_at = sync_source_next_run_at(
        schedule_enabled=source.schedule_enabled,
        schedule_paused=source.schedule_paused,
        is_active=source.is_active,
        schedule_config=source.schedule_config,
    )


def _job_summary_dict(job: Job) -> dict[str, Any]:
    runs_sorted = sorted(job.runs, key=lambda r: r.created_at, reverse=True)
    latest = runs_sorted[0] if runs_sorted else None
    return {
        "id": str(job.id),
        "status": job.status,
        "url": job.url,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "last_run_status": latest.status if latest else None,
        "last_run_error": latest.error_message if latest else None,
        "last_run_id": str(latest.id) if latest else None,
    }


@router.get("", response_model=list[SourcePublic])
async def list_sources(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_bearer)],
    limit: int = Query(default=100, ge=1, le=500),
) -> list[Source]:
    result = await session.execute(
        select(Source)
        .where(Source.organization_id == user.organization_id)
        .order_by(Source.created_at.desc())
        .limit(limit),
    )
    return list(result.scalars().all())


@router.post("", response_model=SourcePublic, status_code=status.HTTP_201_CREATED)
async def create_source(
    body: SourceCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_bearer)],
) -> Source:
    if body.schedule_enabled and body.schedule_config is not None:
        try:
            sched_dump = body.schedule_config.model_dump(mode="json")
            ce = cron_expression_from_source_schedule_config(sched_dump)
            if not ce:
                raise ValueError("Could not resolve cron from schedule_config")
            validate_cron_expression(ce)
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=client_safe_detail(
                    code="invalid_cron",
                    production_message="Invalid schedule configuration.",
                    developer_message=str(exc),
                ),
            ) from exc

    sched_json = body.schedule_config.model_dump(mode="json") if body.schedule_config else None
    row = Source(
        organization_id=user.organization_id,
        created_by_user_id=user.id,
        name=body.name.strip(),
        base_url=str(body.base_url).strip(),
        description=body.description.strip() if body.description is not None else None,
        crawl_type=body.crawl_type,
        allow_external=body.allow_external,
        max_pages=body.max_pages,
        delay_min=body.delay_min,
        delay_max=body.delay_max,
        scrape_engine=body.scrape_engine,
        include_html=body.include_html,
        sitemap_url=str(body.sitemap_url).strip() if body.sitemap_url else None,
        schedule_enabled=body.schedule_enabled,
        schedule_paused=body.schedule_paused,
        schedule_config=sched_json,
        is_active=body.is_active,
    )
    _apply_schedule_fields(row)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


@router.get("/{source_id}", response_model=SourceDetailPublic)
async def get_source(
    source_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_bearer)],
) -> SourceDetailPublic:
    src = await _get_source_org(session, source_id, user.organization_id)
    result = await session.execute(
        select(Job)
        .where(Job.source_id == source_id, Job.organization_id == user.organization_id)
        .order_by(Job.created_at.desc())
        .limit(50)
        .options(selectinload(Job.runs)),
    )
    jobs = list(result.scalars().all())
    base = SourcePublic.model_validate(src)
    return SourceDetailPublic(
        **base.model_dump(),
        recent_jobs=[_job_summary_dict(j) for j in jobs],
    )


@router.put("/{source_id}", response_model=SourcePublic)
async def update_source(
    source_id: UUID,
    body: SourceUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_bearer)],
) -> Source:
    src = await _get_source_org(session, source_id, user.organization_id)
    data = body.model_dump(exclude_unset=True)

    if "schedule_config" in data and data["schedule_config"] is not None:
        try:
            cfg = data["schedule_config"]
            if isinstance(cfg, dict):
                ce = cron_expression_from_source_schedule_config(cfg)
                if ce:
                    validate_cron_expression(ce)
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=client_safe_detail(
                    code="invalid_cron",
                    production_message="Invalid schedule configuration.",
                    developer_message=str(exc),
                ),
            ) from exc

    if "name" in data and data["name"] is not None:
        src.name = str(data["name"]).strip()
    if "base_url" in data and data["base_url"] is not None:
        src.base_url = str(data["base_url"]).strip()
    if "description" in data:
        src.description = data["description"].strip() if data["description"] else None
    if "crawl_type" in data and data["crawl_type"] is not None:
        src.crawl_type = data["crawl_type"]
    if "allow_external" in data and data["allow_external"] is not None:
        src.allow_external = data["allow_external"]
    if "max_pages" in data and data["max_pages"] is not None:
        src.max_pages = data["max_pages"]
    if "delay_min" in data and data["delay_min"] is not None:
        src.delay_min = data["delay_min"]
    if "delay_max" in data and data["delay_max"] is not None:
        src.delay_max = data["delay_max"]
    if "scrape_engine" in data and data["scrape_engine"] is not None:
        src.scrape_engine = data["scrape_engine"]
    if "include_html" in data and data["include_html"] is not None:
        src.include_html = data["include_html"]
    if "sitemap_url" in data:
        su = data["sitemap_url"]
        src.sitemap_url = str(su).strip() if su else None
    if "schedule_enabled" in data and data["schedule_enabled"] is not None:
        src.schedule_enabled = data["schedule_enabled"]
    if "schedule_paused" in data and data["schedule_paused"] is not None:
        src.schedule_paused = data["schedule_paused"]
    if "schedule_config" in data:
        src.schedule_config = data["schedule_config"]
    if "is_active" in data and data["is_active"] is not None:
        src.is_active = data["is_active"]

    if src.delay_max < src.delay_min:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="delay_max must be >= delay_min",
        )

    se = src.schedule_enabled
    if se and not src.schedule_config:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="schedule_config is required when schedule_enabled is true",
        )

    _apply_schedule_fields(src)
    await session.commit()
    await session.refresh(src)
    return src


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_bearer)],
) -> None:
    src = await _get_source_org(session, source_id, user.organization_id)
    await session.delete(src)
    await session.commit()


@router.post("/{source_id}/run", response_model=SourceRunResponse)
async def run_source(
    source_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_bearer)],
) -> SourceRunResponse:
    src = await _get_source_org(session, source_id, user.organization_id)
    if not src.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Source is inactive")

    body = JobCreateRequest(source_id=src.id)
    try:
        payload = build_merged_job_payload(body, src)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    url_str = str(payload["url"])
    settings = ComplianceSettings.from_env()
    correlation_id = uuid.uuid4()
    ctx = ScrapeComplianceContext(
        user_id=str(user.id),
        organization_id=str(user.organization_id),
        audit_correlation_id=str(correlation_id),
        engine=str(payload["engine"]),
        source="api",
    )
    try:
        await asyncio.to_thread(
            run_compliance_before_fetch,
            url_str,
            ctx=ctx,
            settings=settings,
            preverified=False,
            skip_robots_check=bool(payload.get("robots_override")),
        )
    except ComplianceError as exc:
        await record_scrape_audit_event(
            correlation_id=correlation_id,
            source="api",
            user_id=user.id,
            organization_id=user.organization_id,
            url=url_str,
            host=hostname_for_url(url_str) or "invalid",
            engine=str(payload["engine"]),
            step="compliance",
            outcome="denied",
            error_message=str(exc),
        )
        raise compliance_http_exception(exc) from exc

    job, run = await enqueue_scrape_job(
        session=session,
        user=user,
        payload=payload,
        source_id=src.id,
        max_retries=body.max_retries,
        correlation_id=correlation_id,
    )

    await session.execute(
        update(Source)
        .where(Source.id == src.id)
        .values(last_run_at=datetime.now(timezone.utc)),
    )
    await session.commit()

    await record_scrape_audit_event(
        correlation_id=correlation_id,
        source="api",
        user_id=user.id,
        organization_id=user.organization_id,
        url=url_str,
        host=hostname_for_url(url_str) or "invalid",
        engine=str(payload["engine"]),
        step="queue",
        outcome="accepted",
        celery_task_id=job.celery_task_id,
        extra={"job_id": str(job.id), "run_id": str(run.id), "source_id": str(src.id)},
    )

    return SourceRunResponse(
        job_id=job.id,
        run_id=run.id,
        celery_task_id=job.celery_task_id,
        status=job.status,
    )
