from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom_api.db.deps import get_db
from axiom_api.db.models.job_schedule import JobSchedule
from axiom_api.db.models.user import User
from axiom_api.deps.auth import get_current_user_bearer
from axiom_api.schemas.schedules import (
    ScheduleCreateRequest,
    SchedulePublic,
    ScheduleUpdateRequest,
)
from axiom_api.core.public_messages import client_safe_detail
from axiom_api.services.schedule_util import next_fire_time, validate_cron_expression

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("", response_model=list[SchedulePublic])
async def list_schedules(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_bearer)],
    include_paused: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[JobSchedule]:
    q = select(JobSchedule).where(JobSchedule.organization_id == user.organization_id)
    if not include_paused:
        q = q.where(JobSchedule.paused.is_(False))
    q = q.order_by(JobSchedule.created_at.desc()).limit(limit)
    result = await session.execute(q)
    return list(result.scalars().all())


@router.post("", response_model=SchedulePublic, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    body: ScheduleCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_bearer)],
) -> JobSchedule:
    try:
        validate_cron_expression(body.cron_expression)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=client_safe_detail(
                code="invalid_cron",
                production_message="Invalid cron expression.",
                developer_message=str(exc),
            ),
        ) from exc

    payload = body.payload.model_dump(mode="json")
    nr = next_fire_time(body.cron_expression)
    row = JobSchedule(
        organization_id=user.organization_id,
        created_by_user_id=user.id,
        name=body.name,
        cron_expression=body.cron_expression.strip(),
        timezone=body.timezone.strip() or "UTC",
        paused=False,
        payload=payload,
        max_retries=body.max_retries,
        next_run_at=nr,
    )
    session.add(row)
    await session.flush()
    return row


@router.get("/{schedule_id}", response_model=SchedulePublic)
async def get_schedule(
    schedule_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_bearer)],
) -> JobSchedule:
    result = await session.execute(
        select(JobSchedule).where(
            JobSchedule.id == schedule_id,
            JobSchedule.organization_id == user.organization_id,
        ),
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return row


@router.patch("/{schedule_id}", response_model=SchedulePublic)
async def update_schedule(
    schedule_id: UUID,
    body: ScheduleUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_bearer)],
) -> JobSchedule:
    result = await session.execute(
        select(JobSchedule).where(
            JobSchedule.id == schedule_id,
            JobSchedule.organization_id == user.organization_id,
        ),
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    if body.paused is not None:
        row.paused = body.paused
        if not row.paused and row.next_run_at is None:
            row.next_run_at = next_fire_time(row.cron_expression)
    if body.name is not None:
        row.name = body.name
    return row


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_bearer)],
) -> None:
    result = await session.execute(
        select(JobSchedule).where(
            JobSchedule.id == schedule_id,
            JobSchedule.organization_id == user.organization_id,
        ),
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    session.delete(row)
