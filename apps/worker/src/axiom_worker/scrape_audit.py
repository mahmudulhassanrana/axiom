from __future__ import annotations

import logging
import os
import uuid
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


def _sync_database_url() -> str | None:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return None
    if "+asyncpg" in url:
        return url.replace("postgresql+asyncpg", "postgresql", 1)
    return url


def record_scrape_audit_event_sync(
    *,
    correlation_id: UUID,
    source: str,
    user_id: UUID | None,
    organization_id: UUID | None,
    url: str,
    host: str,
    engine: str | None,
    step: str,
    outcome: str,
    http_status: int | None = None,
    error_message: str | None = None,
    celery_task_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    dsn = _sync_database_url()
    if not dsn:
        return
    try:
        import psycopg
        from psycopg.types.json import Json
    except ImportError:
        logger.warning("scrape_audit.psycopg_missing")
        return
    row_id = uuid.uuid4()
    try:
        conn = psycopg.connect(dsn, connect_timeout=5)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO scrape_audit_events (
                        id, correlation_id, source, user_id, organization_id,
                        url, host, engine, step, outcome, http_status,
                        error_message, celery_task_id, extra
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        row_id,
                        correlation_id,
                        source,
                        user_id,
                        organization_id,
                        url,
                        host,
                        engine,
                        step,
                        outcome,
                        http_status,
                        error_message,
                        celery_task_id,
                        Json(extra) if extra is not None else None,
                    ),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        logger.exception(
            "scrape_audit.persist_failed",
            extra={"correlation_id": str(correlation_id), "step": step},
        )
