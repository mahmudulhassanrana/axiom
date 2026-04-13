"""Per-job export downloads (JSON, CSV, PDF)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom_api.db.deps import get_db
from axiom_api.db.models.extracted_data import ExtractedData
from axiom_api.db.models.job import Job
from axiom_api.db.models.run import Run
from axiom_api.db.models.user import User
from axiom_api.deps.auth import get_current_user_bearer
from axiom_api.services.job_export_bundle import (
    job_results_csv_bytes,
    job_results_json_bytes,
    job_results_pdf_bytes,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


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


async def _job_extracted_rows(
    session: AsyncSession,
    job_id: UUID,
    organization_id: UUID,
) -> tuple[Job, list[ExtractedData]]:
    job = await _get_job_for_org(session, job_id, organization_id)
    result = await session.execute(
        select(ExtractedData)
        .join(Run, ExtractedData.run_id == Run.id)
        .where(Run.job_id == job_id)
        .order_by(ExtractedData.created_at.asc()),
    )
    rows = list(result.scalars().all())
    return job, rows


@router.get("/{job_id}/export/json")
async def export_job_json(
    job_id: UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_bearer),
) -> Response:
    job, rows = await _job_extracted_rows(session, job_id, user.organization_id)
    body, mt, ext = job_results_json_bytes(job, rows)
    return Response(
        content=body,
        media_type=mt,
        headers={"Content-Disposition": f'attachment; filename="job-{job_id}.{ext}"', "Cache-Control": "no-store"},
    )


@router.get("/{job_id}/export/csv")
async def export_job_csv(
    job_id: UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_bearer),
) -> Response:
    job, rows = await _job_extracted_rows(session, job_id, user.organization_id)
    body, mt, ext = job_results_csv_bytes(job, rows)
    return Response(
        content=body,
        media_type=mt,
        headers={"Content-Disposition": f'attachment; filename="job-{job_id}.{ext}"', "Cache-Control": "no-store"},
    )


@router.get("/{job_id}/export/pdf")
async def export_job_pdf(
    job_id: UUID,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_bearer),
) -> Response:
    job, rows = await _job_extracted_rows(session, job_id, user.organization_id)
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No extracted data to export")
    try:
        body, mt, ext = job_results_pdf_bytes(job, rows)
    except RuntimeError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return Response(
        content=body,
        media_type=mt,
        headers={"Content-Disposition": f'attachment; filename="job-{job_id}.{ext}"', "Cache-Control": "no-store"},
    )
