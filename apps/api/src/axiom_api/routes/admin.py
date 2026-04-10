from __future__ import annotations

from typing import Annotated

from axiom_compliance import ComplianceSettings
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from axiom_api.core.security import hash_password
from axiom_api.db.deps import get_db
from axiom_api.db.models.job import Job
from axiom_api.db.models.user import User
from axiom_api.deps.auth import RequireAdmin
from axiom_api.schemas.admin import (
    AdminCreateUserRequest,
    AdminStatsResponse,
    ComplianceDomainsResponse,
)
from axiom_api.schemas.auth import UserPublic
from axiom_api.schemas.jobs import JobPublic

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/ping")
async def admin_ping(_admin: RequireAdmin) -> dict[str, str]:
    return {"scope": "admin"}


@router.get("/stats", response_model=AdminStatsResponse)
async def admin_stats(
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: RequireAdmin,
) -> AdminStatsResponse:
    q = (
        select(Job.status, func.count())
        .where(Job.organization_id == admin.organization_id)
        .group_by(Job.status)
    )
    rows = (await session.execute(q)).all()
    by_status = {str(r[0]): int(r[1]) for r in rows}
    total = sum(by_status.values())
    return AdminStatsResponse(
        total_jobs=total,
        by_status=by_status,
        failed_jobs=by_status.get("failed", 0),
    )


@router.get("/jobs/failed", response_model=list[JobPublic])
async def admin_failed_jobs(
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: RequireAdmin,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Job]:
    result = await session.execute(
        select(Job)
        .where(Job.organization_id == admin.organization_id, Job.status == "failed")
        .order_by(Job.updated_at.desc())
        .limit(limit),
    )
    return list(result.scalars().all())


@router.get("/compliance/domains", response_model=ComplianceDomainsResponse)
async def admin_compliance_domains(_admin: RequireAdmin) -> ComplianceDomainsResponse:
    s = ComplianceSettings.from_env()
    return ComplianceDomainsResponse(
        blocklist=sorted(s.domain_blocklist),
        allowlist=sorted(s.domain_allowlist),
    )


@router.post("/users", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def admin_create_user(
    body: AdminCreateUserRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: RequireAdmin,
) -> User:
    user = User(
        organization_id=admin.organization_id,
        email=str(body.email).lower().strip(),
        password_hash=hash_password(body.password),
        full_name=body.full_name.strip() if body.full_name else None,
        role=body.role,
        is_active=True,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc
    await session.refresh(user)
    return user
