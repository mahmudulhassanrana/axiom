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


def _undefined_column(exc: BaseException) -> bool:
    if type(exc).__name__ == "UndefinedColumn":
        return True
    try:
        from psycopg.errors import UndefinedColumn

        return isinstance(exc, UndefinedColumn)
    except ImportError:
        pass
    msg = str(exc).lower()
    return "extracted_data" in msg and "does not exist" in msg


def insert_extracted_data(run_id: UUID, doc: dict[str, Any]) -> None:
    """Insert one row; ``doc`` is ``ExtractedDocument.to_json_dict()`` plus worker enrichments."""
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
        "file_links",
        "structured_entities",
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

    images_val = doc.get("images") if isinstance(doc.get("images"), list) else None
    file_links_val = doc.get("file_links")
    if not isinstance(file_links_val, list):
        file_links_val = doc.get("files") if isinstance(doc.get("files"), list) else None
    struct_val = doc.get("structured_entities") if isinstance(doc.get("structured_entities"), dict) else None
    ext_type = doc.get("extraction_type")
    if ext_type is not None:
        ext_type = str(ext_type)[:32] if str(ext_type).strip() else None
    crawl_depth = doc.get("crawl_depth")
    if crawl_depth is None and isinstance(meta.get("crawl_depth"), (int, float, str)):
        try:
            crawl_depth = int(meta["crawl_depth"])
        except (TypeError, ValueError):
            crawl_depth = None
    elif crawl_depth is not None:
        try:
            crawl_depth = int(crawl_depth)
        except (TypeError, ValueError):
            crawl_depth = None

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

    extended_sql = """
        INSERT INTO extracted_data (
            id, run_id, source_url, final_url, title, text_content,
            payload, extractor_kind, http_status,
            country, city, published_date,
            images, file_links, structured_entities, extraction_type, crawl_depth, is_restricted,
            created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
        )
        """
    extended_params = base_params + (
        country,
        city,
        published_date,
        Json(images_val) if images_val is not None else None,
        Json(file_links_val) if file_links_val is not None else None,
        Json(struct_val) if struct_val is not None else None,
        ext_type,
        crawl_depth,
        False,
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

    attempts: list[tuple[str, tuple[Any, ...]]] = [
        (extended_sql, extended_params),
        (full_sql, base_params + (country, city, published_date)),
        (legacy_sql, base_params),
    ]

    try:
        conn = psycopg.connect(dsn, connect_timeout=10)
        try:
            last_exc: BaseException | None = None
            for sql, params in attempts:
                try:
                    with conn.cursor() as cur:
                        cur.execute(sql, params)
                    conn.commit()
                    last_exc = None
                    break
                except Exception as exc:
                    conn.rollback()
                    last_exc = exc
                    if not _undefined_column(exc):
                        raise
                    logger.warning(
                        "extracted_persistence.insert_fallback",
                        extra={"run_id": str(run_id), "detail": str(exc)[:200]},
                    )
            if last_exc is not None:
                raise last_exc
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
