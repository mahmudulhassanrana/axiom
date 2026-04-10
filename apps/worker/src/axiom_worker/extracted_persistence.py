"""Persist ExtractedDocument rows into ``extracted_data`` (sync psycopg)."""

from __future__ import annotations

import logging
import uuid
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


def insert_extracted_data(run_id: UUID, doc: dict[str, Any]) -> None:
    """Insert one row; ``doc`` is ``ExtractedDocument.to_json_dict()``."""
    from axiom_worker.db_sync import get_psycopg_dsn

    dsn = get_psycopg_dsn()
    if not dsn:
        msg = "DATABASE_URL is not set; cannot persist extracted data for this run"
        logger.error("extracted_persistence.no_database_url", extra={"run_id": str(run_id)})
        raise RuntimeError(msg)
    try:
        import psycopg
        from psycopg.types.json import Json
    except ImportError as exc:
        msg = "psycopg is required to persist extracted data"
        logger.error("extracted_persistence.psycopg_missing", extra={"run_id": str(run_id)})
        raise RuntimeError(msg) from exc

    links = doc.get("links") or []
    meta = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    payload: dict[str, Any] = {
        "links": links,
        "metadata": meta,
        "language": doc.get("language"),
        "fetched_at": doc.get("fetched_at"),
    }
    row_id = uuid.uuid4()
    source_url = str(doc.get("url") or "")
    final_url = doc.get("final_url")
    title = doc.get("title")
    text_content = doc.get("text")
    extractor_kind = str(doc.get("extractor_kind") or "html_requests")
    http_status = doc.get("http_status")

    try:
        conn = psycopg.connect(dsn, connect_timeout=10)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO extracted_data (
                        id, run_id, source_url, final_url, title, text_content,
                        payload, extractor_kind, http_status, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
                    )
                    """,
                    (
                        str(row_id),
                        str(run_id),
                        source_url,
                        final_url,
                        title,
                        text_content,
                        Json(payload),
                        extractor_kind,
                        http_status,
                    ),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        logger.exception("extracted_persistence.insert_failed", extra={"run_id": str(run_id)})
        raise

    logger.info(
        "Data saved run_id=%s extracted_data_id=%s extractor_kind=%s",
        run_id,
        row_id,
        extractor_kind,
        extra={
            "run_id": str(run_id),
            "extracted_data_id": str(row_id),
            "extractor_kind": extractor_kind,
        },
    )
