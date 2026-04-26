from __future__ import annotations

import logging
from typing import Any, Literal
from uuid import UUID

from axiom_worker.db_sync import get_psycopg_dsn

logger = logging.getLogger(__name__)

ClaimOutcome = Literal["claimed", "completed", "failed", "already_running", "restricted"]


def claim_run_for_scrape(run_id: UUID, job_id: UUID, *, celery_retries: int) -> ClaimOutcome:
    """
    Move ``pending``/``queued`` → ``running`` once. If already ``completed``/``failed``, report that.
    If ``running`` and ``celery_retries == 0``, treat as duplicate parallel task (skip).
    If ``running`` and retries > 0, allow the same task to continue after a transient failure.
    """
    dsn = get_psycopg_dsn()
    if not dsn:
        logger.error(
            "job_status.no_database_url",
            extra={"run_id": str(run_id), "job_id": str(job_id)},
        )
        raise RuntimeError(
            "DATABASE_URL is not set; worker cannot persist job/run status. "
            "Use the same DATABASE_URL as the API (see repo root .env)."
        )
    try:
        import psycopg
    except ImportError as exc:
        logger.error("job_status.psycopg_missing", extra={"run_id": str(run_id)})
        raise RuntimeError(
            "psycopg is required for job status updates; install axiom-worker dependencies."
        ) from exc
    try:
        conn = psycopg.connect(dsn, connect_timeout=5)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE runs
                    SET status = 'running',
                        started_at = COALESCE(started_at, NOW()),
                        updated_at = NOW()
                    WHERE id = %s AND status IN ('pending', 'queued')
                    RETURNING id
                    """,
                    (str(run_id),),
                )
                row = cur.fetchone()
                if row:
                    cur.execute(
                        "UPDATE jobs SET status = 'running', updated_at = NOW() WHERE id = %s",
                        (str(job_id),),
                    )
                    conn.commit()
                    logger.info(
                        "Updating job to running job_id=%s run_id=%s",
                        job_id,
                        run_id,
                    )
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
                if st == "restricted":
                    conn.rollback()
                    return "restricted"
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
        raise


def load_completed_scrape_document(run_id: UUID) -> dict[str, Any] | None:
    """Return stored extraction JSON for a completed run, or ``None``."""
    dsn = get_psycopg_dsn()
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
    dsn = get_psycopg_dsn()
    if not dsn:
        logger.error(
            "job_status.mark_running_no_database_url",
            extra={"run_id": str(run_id), "job_id": str(job_id)},
        )
        raise RuntimeError("DATABASE_URL is not set; cannot mark job running.")
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("psycopg is required for job status updates.") from exc
    try:
        conn = psycopg.connect(dsn, connect_timeout=5)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE runs SET status = 'running',
                        started_at = COALESCE(started_at, NOW()),
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (str(run_id),),
                )
                cur.execute(
                    "UPDATE jobs SET status = 'running', updated_at = NOW() WHERE id = %s",
                    (str(job_id),),
                )
            conn.commit()
            logger.info("Updating job to running job_id=%s run_id=%s", job_id, run_id)
        finally:
            conn.close()
    except Exception:
        logger.exception("job_status.mark_running_failed", extra={"run_id": str(run_id)})
        raise


def mark_restricted(run_id: UUID, job_id: UUID, message: str, *, metrics: dict[str, Any] | None = None) -> None:
    """Job/run stopped by policy (e.g. robots.txt) without persisting extracted pages."""
    dsn = get_psycopg_dsn()
    if not dsn:
        logger.error(
            "job_status.mark_restricted_no_database_url",
            extra={"run_id": str(run_id), "job_id": str(job_id)},
        )
        return
    try:
        import psycopg
        from psycopg.types.json import Json
    except ImportError as exc:
        raise RuntimeError("psycopg is required for job status updates.") from exc
    m = dict(metrics or {})
    m["compliance"] = "robots_denied"
    try:
        conn = psycopg.connect(dsn, connect_timeout=5)
        try:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        """
                        UPDATE runs SET status = 'restricted', completed_at = NOW(), error_message = %s,
                            metrics = %s, updated_at = NOW()
                        WHERE id = %s
                        """,
                        (message, Json(m), str(run_id)),
                    )
                    cur.execute(
                        """
                        UPDATE jobs SET status = 'restricted', is_restricted = true, updated_at = NOW()
                        WHERE id = %s
                        """,
                        (str(job_id),),
                    )
                except Exception as exc:
                    conn.rollback()
                    if not _is_missing_job_restricted_column(exc):
                        raise
                    with conn.cursor() as cur2:
                        cur2.execute(
                            """
                            UPDATE runs SET status = 'restricted', completed_at = NOW(), error_message = %s,
                                metrics = %s, updated_at = NOW()
                            WHERE id = %s
                            """,
                            (message, Json(m), str(run_id)),
                        )
                        cur2.execute(
                            "UPDATE jobs SET status = 'restricted', updated_at = NOW() WHERE id = %s",
                            (str(job_id),),
                        )
            conn.commit()
            logger.info(
                "job_status.mark_restricted done job_id=%s run_id=%s",
                job_id,
                run_id,
            )
        finally:
            conn.close()
    except Exception:
        logger.exception("job_status.mark_restricted_failed", extra={"run_id": str(run_id)})
        raise


def _is_missing_job_restricted_column(exc: BaseException) -> bool:
    if type(exc).__name__ == "UndefinedColumn":
        return True
    try:
        from psycopg.errors import UndefinedColumn

        if isinstance(exc, UndefinedColumn):
            return True
    except ImportError:
        pass
    msg = str(exc).lower()
    return "is_restricted" in msg and "does not exist" in msg


def mark_succeeded(run_id: UUID, job_id: UUID, metrics: dict[str, Any]) -> None:
    dsn = get_psycopg_dsn()
    if not dsn:
        logger.error(
            "job_status.mark_succeeded_no_database_url",
            extra={"run_id": str(run_id), "job_id": str(job_id)},
        )
        raise RuntimeError("DATABASE_URL is not set; cannot mark job completed.")
    try:
        import psycopg
        from psycopg.types.json import Json
    except ImportError as exc:
        raise RuntimeError("psycopg is required for job status updates.") from exc
    try:
        conn = psycopg.connect(dsn, connect_timeout=5)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE runs SET status = 'completed', completed_at = NOW(), metrics = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (Json(metrics), str(run_id)),
                )
                cur.execute(
                    "UPDATE jobs SET status = 'completed', updated_at = NOW() WHERE id = %s",
                    (str(job_id),),
                )
            conn.commit()
            logger.info("Updating job to completed job_id=%s run_id=%s", job_id, run_id)
        finally:
            conn.close()
    except Exception:
        logger.exception("job_status.mark_succeeded_failed", extra={"run_id": str(run_id)})
        raise


def mark_failed(run_id: UUID, job_id: UUID, error: str) -> None:
    dsn = get_psycopg_dsn()
    if not dsn:
        logger.error(
            "job_status.mark_failed_no_database_url",
            extra={"run_id": str(run_id), "job_id": str(job_id)},
        )
        return
    try:
        import psycopg
    except ImportError as exc:
        logger.error("job_status.mark_failed_psycopg_missing", extra={"run_id": str(run_id)})
        raise RuntimeError("psycopg is required for job status updates.") from exc
    try:
        conn = psycopg.connect(dsn, connect_timeout=5)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE runs SET status = 'failed', completed_at = NOW(), error_message = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (error, str(run_id)),
                )
                cur.execute(
                    "UPDATE jobs SET status = 'failed', updated_at = NOW() WHERE id = %s",
                    (str(job_id),),
                )
            conn.commit()
            logger.info(
                "Job failed job_id=%s run_id=%s error=%s",
                job_id,
                run_id,
                (error[:500] + "…") if len(error) > 500 else error,
            )
        finally:
            conn.close()
    except Exception:
        logger.exception("job_status.mark_failed_failed", extra={"run_id": str(run_id)})
        raise
