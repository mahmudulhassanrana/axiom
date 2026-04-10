"""Application lifespan: logging hooks on startup/shutdown."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from axiom_api.core.deployment_security import verify_deployment_security
from axiom_api.core.logging_setup import log_service_start, log_service_stop

logger = logging.getLogger("axiom_api")


async def _probe_database_optional() -> None:
    """Log whether PostgreSQL is reachable; do not block startup."""
    try:
        from axiom_api.db.session import get_engine

        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning(
            "database_unreachable",
            extra={"event": "database_unreachable", "error": str(exc)},
        )
        return
    logger.info("database_ready", extra={"event": "database_ready"})
    try:
        from axiom_api.db.bootstrap import ensure_schema_and_seed

        await ensure_schema_and_seed()
    except Exception as exc:
        logger.warning(
            "database_bootstrap_failed",
            extra={"event": "database_bootstrap_failed", "error": str(exc)},
        )


@asynccontextmanager
async def app_lifespan(_app: FastAPI):
    verify_deployment_security()
    await _probe_database_optional()
    log_service_start()
    yield
    log_service_stop()
