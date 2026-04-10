"""Persist ExtractedDocument rows into ``extracted_data`` (sync psycopg)."""

from __future__ import annotations

import logging
import uuid
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


def _dsn() -> str | None:
    import os

    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return None
    if "+asyncpg" in url:
        return url.replace("postgresql+asyncpg", "postgresql", 1)
    return url


def insert_extracted_data(run_id: UUID, doc: dict[str, Any]) -> None:
    """Insert one row; ``doc`` is ``ExtractedDocument.to_json_dict()``."""
    dsn = _dsn()
    if not dsn:
        logger.warning("extracted_persistence.skip_no_database_url", extra={"run_id": str(run_id)})
        return
    try:
        import psycopg
        from psycopg.types.json import Json
    except ImportError:
        logger.warning("extracted_persistence.psycopg_missing")
        return

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
        "extracted_persistence.saved",
        extra={
            "run_id": str(run_id),
            "extracted_data_id": str(row_id),
            "extractor_kind": extractor_kind,
        },
    )
