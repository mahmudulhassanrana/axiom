from __future__ import annotations

import logging
import os
from typing import Any, Literal
from uuid import UUID

logger = logging.getLogger(__name__)

ClaimOutcome = Literal["claimed", "completed", "failed", "already_running"]


def _dsn() -> str | None:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return None
    if "+asyncpg" in url:
        return url.replace("postgresql+asyncpg", "postgresql", 1)
    return url


def claim_run_for_scrape(run_id: UUID, job_id: UUID, *, celery_retries: int) -> ClaimOutcome:
    """
    Move ``pending``/``queued`` → ``running`` once. If already ``completed``/``failed``, report that.
    If ``running`` and ``celery_retries == 0``, treat as duplicate parallel task (skip).
    If ``running`` and retries > 0, allow the same task to continue after a transient failure.
    """
    dsn = _dsn()
    if not dsn:
        return "claimed"
    try:
        import psycopg
    except ImportError:
        logger.warning("job_status.psycopg_missing")
        return "claimed"
    try:
        conn = psycopg.connect(dsn, connect_timeout=5)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE runs
                    SET status = 'running', started_at = COALESCE(started_at, NOW())
                    WHERE id = %s AND status IN ('pending', 'queued')
                    RETURNING id
                    """,
                    (str(run_id),),
                )
                row = cur.fetchone()
                if row:
                    cur.execute(
                        "UPDATE jobs SET status = 'running' WHERE id = %s",
                        (str(job_id),),
                    )
                    conn.commit()
                    return "claimed"
                cur.execute("SELECT status FROM runs WHERE id = %s", (str(run_id),))
                st_row = cur.fetchone()
                if not st_row:
                    conn.rollback()
                    return "failed"
                st = st_row[0]
                if st == "completed":
                    conn.rollback()
                    return "completed"
                if st == "failed":
                    conn.rollback()
                    return "failed"
                if st == "running":
                    conn.rollback()
                    if celery_retries > 0:
                        return "claimed"
                    return "already_running"
                conn.rollback()
                return "claimed"
        finally:
            conn.close()
    except Exception:
        logger.exception("job_status.claim_run_failed", extra={"run_id": str(run_id)})
        return "claimed"


def load_completed_scrape_document(run_id: UUID) -> dict[str, Any] | None:
    """Return stored extraction JSON for a completed run, or ``None``."""
    dsn = _dsn()
    if not dsn:
        return None
    try:
        import psycopg
    except ImportError:
        return None
    try:
        conn = psycopg.connect(dsn, connect_timeout=5)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT source_url, final_url, title, text_content, payload, extractor_kind, http_status
                    FROM extracted_data
                    WHERE run_id = %s
                    ORDER BY created_at ASC
                    LIMIT 1
                    """,
                    (str(run_id),),
                )
                row = cur.fetchone()
                if not row:
                    return None
                source_url, final_url, title, text_content, payload, extractor_kind, http_status = row
                pl = payload if isinstance(payload, dict) else {}
                links = pl.get("links") or []
                meta = pl.get("metadata") if isinstance(pl.get("metadata"), dict) else {}
                out: dict[str, Any] = {
                    "url": source_url,
                    "final_url": final_url,
                    "title": title,
                    "text": text_content or "",
                    "links": links,
                    "extractor_kind": extractor_kind or "html_requests",
                    "http_status": http_status,
                    "metadata": meta,
                    "language": pl.get("language"),
                    "fetched_at": pl.get("fetched_at"),
                }
                return out
        finally:
            conn.close()
    except Exception:
        logger.exception("job_status.load_completed_failed", extra={"run_id": str(run_id)})
        return None


def mark_running(run_id: UUID, job_id: UUID) -> None:
    """Legacy path: ensure run/job marked running (used if claim skipped without DB)."""
    dsn = _dsn()
    if not dsn:
        return
    try:
        import psycopg
    except ImportError:
        logger.warning("job_status.psycopg_missing")
        return
    try:
        conn = psycopg.connect(dsn, connect_timeout=5)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE runs SET status = 'running', started_at = COALESCE(started_at, NOW())
                    WHERE id = %s
                    """,
                    (str(run_id),),
                )
                cur.execute(
                    "UPDATE jobs SET status = 'running' WHERE id = %s",
                    (str(job_id),),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        logger.exception("job_status.mark_running_failed", extra={"run_id": str(run_id)})


def mark_succeeded(run_id: UUID, job_id: UUID, metrics: dict[str, Any]) -> None:
    dsn = _dsn()
    if not dsn:
        return
    try:
        import psycopg
        from psycopg.types.json import Json
    except ImportError:
        logger.warning("job_status.psycopg_missing")
        return
    try:
        conn = psycopg.connect(dsn, connect_timeout=5)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE runs SET status = 'completed', completed_at = NOW(), metrics = %s
                    WHERE id = %s
                    """,
                    (Json(metrics), str(run_id)),
                )
                cur.execute(
                    "UPDATE jobs SET status = 'completed' WHERE id = %s",
                    (str(job_id),),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        logger.exception("job_status.mark_succeeded_failed", extra={"run_id": str(run_id)})


def mark_failed(run_id: UUID, job_id: UUID, error: str) -> None:
    dsn = _dsn()
    if not dsn:
        return
    try:
        import psycopg
    except ImportError:
        logger.warning("job_status.psycopg_missing")
        return
    try:
        conn = psycopg.connect(dsn, connect_timeout=5)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE runs SET status = 'failed', completed_at = NOW(), error_message = %s
                    WHERE id = %s
                    """,
                    (error, str(run_id)),
                )
                cur.execute(
                    "UPDATE jobs SET status = 'failed' WHERE id = %s",
                    (str(job_id),),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        logger.exception("job_status.mark_failed_failed", extra={"run_id": str(run_id)})
