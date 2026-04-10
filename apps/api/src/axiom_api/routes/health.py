from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from axiom_api.db.deps import get_db
from axiom_api.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns 200 when the process is up. Use for liveness probes.",
)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=None,
    summary="Readiness probe",
    description="Returns 200 when PostgreSQL is reachable; 503 otherwise.",
)
async def ready(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str] | JSONResponse:
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unready", "database": "disconnected"},
        )
    return {"status": "ok", "database": "connected"}
