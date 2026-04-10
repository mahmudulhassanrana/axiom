from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from axiom_api.db.deps import get_db
from axiom_api.db.models.job import Job
from axiom_api.db.models.run import Run
from axiom_api.db.models.user import User
from axiom_api.deps.auth import get_current_user_bearer
from axiom_api.schemas.jobs import RunDetailPublic

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get(
    "/{run_id}",
    response_model=RunDetailPublic,
    summary="Get run",
    description="Run detail with extracted rows (requires Bearer JWT).",
)
async def get_run_detail(
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
