"""Create Job + Run rows and dispatch ``axiom.scrape`` (shared by /jobs and /sources/.../run)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from kombu.exceptions import OperationalError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom_api.celery_client import AXIOM_QUEUE, get_celery_app
from axiom_api.core.public_messages import client_safe_detail
from axiom_api.db.models.job import Job
from axiom_api.db.models.run import Run
from axiom_api.db.models.user import User
from axiom_api.services.scrape_audit import record_scrape_audit_event

logger = logging.getLogger("axiom_api.scrape_job_enqueue")


def _celery_kwargs_from_payload(
    payload: dict[str, Any],
    *,
    user_id: UUID,
    organization_id: UUID,
    audit_correlation_id: UUID,
    job_id: UUID,
    run_id: UUID,
    max_retries: int,
    schedule_id: UUID | None = None,
) -> dict[str, Any]:
    return {
        "url": str(payload["url"]),
        "engine": str(payload["engine"]),
        "include_html": bool(payload["include_html"]),
        "user_id": str(user_id),
        "organization_id": str(organization_id),
        "audit_correlation_id": str(audit_correlation_id),
        "compliance_preverified": True,
        "job_id": str(job_id),
        "run_id": str(run_id),
        "max_retries_override": max_retries,
        "crawl_max_pages": int(payload["crawl_max_pages"]),
        "crawl_delay_seconds": float(payload["crawl_delay_seconds"]),
        "crawl_jitter_seconds": float(payload["crawl_jitter_seconds"]),
        "crawl_allow_external": bool(payload["crawl_allow_external"]),
        "crawl_max_external_pages": int(payload["crawl_max_external_pages"]),
        "crawl_max_external_per_host": int(payload["crawl_max_external_per_host"]),
        "pre_fetch_jitter_max_seconds": float(payload["pre_fetch_jitter_max_seconds"]),
        "crawl_type": str(payload.get("crawl_type") or "single_page"),
        "sitemap_url": payload.get("sitemap_url"),
        **({"schedule_id": str(schedule_id)} if schedule_id else {}),
    }


async def enqueue_scrape_job(
    *,
    session: AsyncSession,
    user: User,
    payload: dict[str, Any],
    source_id: UUID | None,
    max_retries: int,
    correlation_id: UUID,
    schedule_id: UUID | None = None,
) -> tuple[Job, Run]:
    url_str = str(payload["url"])
    dup = await session.execute(
        select(Job.id).where(
            Job.organization_id == user.organization_id,
            Job.url == url_str,
            Job.kind == "scrape",
            Job.status.in_(("pending", "queued", "running")),
        ).limit(1),
    )
    if dup.scalar_one_or_none() is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="A scrape for this URL is already queued or running for your workspace.",
        )

    job = Job(
        organization_id=user.organization_id,
        source_id=source_id,
        schedule_id=schedule_id,
        kind="scrape",
        url=url_str,
        status="pending",
        payload=dict(payload),
    )
    session.add(job)
    await session.flush()

    run = Run(job_id=job.id, status="pending")
    session.add(run)
    await session.flush()

    await session.commit()
    await session.refresh(job)
    await session.refresh(run)

    celery_app = get_celery_app()
    try:
        async_result = celery_app.send_task(
            "axiom.scrape",
            kwargs=_celery_kwargs_from_payload(
                payload,
                user_id=user.id,
                organization_id=user.organization_id,
                audit_correlation_id=correlation_id,
                job_id=job.id,
                run_id=run.id,
                max_retries=max_retries,
                schedule_id=schedule_id,
            ),
            queue=AXIOM_QUEUE,
        )
    except OperationalError as exc:
        job.status = "failed"
        run.status = "failed"
        run.error_message = "Celery broker unavailable"
        await session.commit()
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=client_safe_detail(
                code="service_unavailable",
                production_message=(
                    "The task queue is temporarily unavailable. Please try again later."
                ),
                developer_message=f"Celery broker unavailable: {exc}",
            ),
        ) from exc

    job.celery_task_id = async_result.id
    job.status = "queued"
    run.status = "queued"
    await session.commit()
    await session.refresh(job)
    await session.refresh(run)
    logger.info(
        "Job created job_id=%s run_id=%s celery_task_id=%s url=%s",
        job.id,
        run.id,
        async_result.id,
        url_str,
    )
    return job, run
