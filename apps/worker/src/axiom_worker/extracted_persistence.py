"""Persist ExtractedDocument rows into ``extracted_data`` (sync psycopg)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


def _meta_str(meta: dict[str, Any], *keys: str) -> str | None:
    for k in keys:
        v = meta.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _parse_published(meta: dict[str, Any]) -> datetime | None:
    for k in ("published_date", "article_published_time", "datePublished", "pubdate", "published"):
        v = meta.get(k)
        if v is None:
            continue
        if isinstance(v, (int, float)):
            try:
                return datetime.fromtimestamp(float(v), tz=timezone.utc)
            except (ValueError, OSError):
                continue
        s = str(v).strip()
        if not s:
            continue
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            continue
    return None


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
    meta = dict(doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {})
    payload: dict[str, Any] = {
        "links": links,
        "metadata": meta,
        "language": doc.get("language"),
        "fetched_at": doc.get("fetched_at"),
    }
    for key in (
        "page_url",
        "images",
        "files",
    ):
        if key in doc and doc[key] is not None:
            payload[key] = doc[key]
    row_id = uuid.uuid4()
    source_url = str(doc.get("url") or "")
    final_url = doc.get("final_url")
    title = doc.get("title")
    text_content = doc.get("text")
    extractor_kind = str(doc.get("extractor_kind") or "html_requests")
    http_status = doc.get("http_status")
    country = _meta_str(meta, "country", "geo_country", "location_country")
    city = _meta_str(meta, "city", "geo_city", "location_city")
    published_date = _parse_published(meta)

    base_params = (
        str(row_id),
        str(run_id),
        source_url,
        final_url,
        title,
        text_content,
        Json(payload),
        extractor_kind,
        http_status,
    )
    full_sql = """
                    INSERT INTO extracted_data (
                        id, run_id, source_url, final_url, title, text_content,
                        payload, extractor_kind, http_status,
                        country, city, published_date,
                        created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
                    )
                    """
    legacy_sql = """
                    INSERT INTO extracted_data (
                        id, run_id, source_url, final_url, title, text_content,
                        payload, extractor_kind, http_status,
                        created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
                    )
                    """

    try:
        conn = psycopg.connect(dsn, connect_timeout=10)
        try:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        full_sql,
                        base_params + (country, city, published_date),
                    )
                conn.commit()
            except Exception as exc:
                conn.rollback()
                if _is_missing_extracted_column(exc):
                    logger.warning(
                        "extracted_persistence.legacy_insert_no_location_columns",
                        extra={"run_id": str(run_id)},
                    )
                    with conn.cursor() as cur:
                        cur.execute(legacy_sql, base_params)
                    conn.commit()
                else:
                    raise
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


def _is_missing_extracted_column(exc: BaseException) -> bool:
    if type(exc).__name__ == "UndefinedColumn":
        return True
    try:
        from psycopg.errors import UndefinedColumn

        if isinstance(exc, UndefinedColumn):
            return True
    except ImportError:
        pass
    msg = str(exc).lower()
    return "extracted_data" in msg and "does not exist" in msg and (
        "country" in msg or "city" in msg or "published_date" in msg
    )
