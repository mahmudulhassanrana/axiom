from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Annotated
from uuid import UUID

from axiom_compliance import ComplianceSettings, ScrapeComplianceContext
from axiom_compliance.exceptions import ComplianceError
from axiom_compliance.lists import hostname_for_url
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from axiom_api.core.compliance_fetch import run_compliance_before_fetch
from axiom_api.core.compliance_http import compliance_http_exception
from axiom_api.db.deps import get_db
from axiom_api.db.models.extracted_data import ExtractedData
from axiom_api.db.models.job import Job
from axiom_api.db.models.run import Run
from axiom_api.db.models.scrape_audit_event import ScrapeAuditEvent
from axiom_api.db.models.source import Source
from axiom_api.db.models.user import User
from axiom_api.deps.auth import get_current_user_bearer
from axiom_api.schemas.jobs import (
    AuditLogEntryPublic,
    ExtractedDataPublic,
    JobCreateRequest,
    JobDetailPublic,
    JobPublic,
    RunDetailPublic,
    RunPublic,
)
from axiom_api.services.job_payload_merge import build_merged_job_payload
from axiom_api.services.scrape_audit import record_scrape_audit_event
from axiom_api.services.scrape_job_enqueue import enqueue_scrape_job

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = logging.getLogger("axiom_api.jobs")


async def _get_job_for_org(
    session: AsyncSession,
    job_id: UUID,
    organization_id: UUID,
) -> Job:
    result = await session.execute(
        select(Job).where(Job.id == job_id, Job.organization_id == organization_id),
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.get(
    "",
    response_model=list[JobPublic],
    summary="List jobs",
    description="Jobs for the authenticated user's organization (newest first).",
)
async def list_jobs(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_bearer)],
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Job]:
    result = await session.execute(
        select(Job)
        .where(Job.organization_id == user.organization_id)
        .order_by(Job.created_at.desc())
        .limit(limit),
    )
    return list(result.scalars().all())


@router.post(
    "",
    response_model=JobPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create job",
    description="Create a scrape job, enqueue a Celery task, and return the job row.",
)
async def create_job(
    body: JobCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_bearer)],
) -> Job:
    settings = ComplianceSettings.from_env()
    source: Source | None = None
    if body.source_id is not None:
        source = await session.get(Source, body.source_id)
        if source is None or source.organization_id != user.organization_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Source not found")
    try:
        payload = build_merged_job_payload(body, source)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    url_str = str(payload["url"])
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
        source_id=body.source_id,
        max_retries=body.max_retries,
        correlation_id=correlation_id,
    )
    logger.info(
        "Job created job_id=%s run_id=%s celery_task_id=%s url=%s",
        job.id,
        run.id,
        job.celery_task_id,
        url_str,
        extra={
            "event": "job_created",
            "job_id": str(job.id),
            "run_id": str(run.id),
            "organization_id": str(user.organization_id),
            "celery_task_id": job.celery_task_id,
            "url": url_str,
        },
    )
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
        extra={"job_id": str(job.id), "run_id": str(run.id)},
    )
    return job


@router.get(
    "/{job_id}/results",
    response_model=list[ExtractedDataPublic],
    summary="Job extraction results",
    description="Persisted extracted rows for all runs of this job (newest first).",
)
async def job_results(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_bearer)],
) -> list[ExtractedData]:
    await _get_job_for_org(session, job_id, user.organization_id)
    result = await session.execute(
        select(ExtractedData)
        .join(Run, ExtractedData.run_id == Run.id)
        .where(Run.job_id == job_id)
        .order_by(ExtractedData.created_at.desc()),
    )
    rows = list(result.scalars().all())
    logger.info("API response sent: job_results job_id=%s rows=%s", job_id, len(rows))
    return rows


@router.get(
    "/{job_id}",
    response_model=JobDetailPublic,
    summary="Get job",
    description="Job detail including runs and extracted payloads for each run.",
)
async def get_job(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_bearer)],
) -> Job:
    result = await session.execute(
        select(Job)
        .options(selectinload(Job.runs).selectinload(Run.extracted_data))
        .where(Job.id == job_id, Job.organization_id == user.organization_id)
        .execution_options(populate_existing=True),
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Job not found")
    job.runs.sort(key=lambda r: r.created_at, reverse=True)
    return job


@router.get(
    "/{job_id}/runs",
    response_model=list[RunPublic],
    summary="List runs for job",
)
async def list_runs(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_bearer)],
) -> list[Run]:
    await _get_job_for_org(session, job_id, user.organization_id)
    result = await session.execute(
        select(Run).where(Run.job_id == job_id).order_by(Run.created_at.desc()),
    )
    return list(result.scalars().all())


@router.get(
    "/{job_id}/logs",
    response_model=list[AuditLogEntryPublic],
    summary="Job audit log",
)
async def job_logs(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_bearer)],
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ScrapeAuditEvent]:
    job = await _get_job_for_org(session, job_id, user.organization_id)
    org = ScrapeAuditEvent.organization_id == user.organization_id
    by_extra = and_(
        org,
        ScrapeAuditEvent.extra.is_not(None),
        ScrapeAuditEvent.extra.contains({"job_id": str(job_id)}),
    )
    if job.celery_task_id:
        filter_expr = or_(by_extra, and_(org, ScrapeAuditEvent.celery_task_id == job.celery_task_id))
    else:
        filter_expr = by_extra
    result = await session.execute(
        select(ScrapeAuditEvent)
        .where(filter_expr)
        .order_by(ScrapeAuditEvent.created_at.desc())
        .limit(limit),
    )
    return list(result.scalars().all())


@router.get(
    "/runs/{run_id}",
    response_model=RunDetailPublic,
    summary="Get run (nested under jobs)",
    description="Prefer ``GET /runs/{run_id}``; this path is kept for compatibility.",
)
async def get_run(
    run_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_bearer)],
) -> Run:
    result = await session.execute(
        select(Run)
        .join(Job)
        .options(selectinload(Run.extracted_data))
        .where(Run.id == run_id, Job.organization_id == user.organization_id),
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run
