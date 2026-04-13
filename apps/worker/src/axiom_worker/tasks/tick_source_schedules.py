from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import psycopg
from croniter import croniter
from psycopg.rows import dict_row

from axiom_compliance import ComplianceSettings, ScrapeComplianceContext, run_compliance_before_fetch
from axiom_compliance.exceptions import ComplianceError
from axiom_compliance.lists import hostname_for_url
from axiom_worker.celery_app import app as celery_app
from axiom_worker.db_sync import get_psycopg_dsn
from axiom_worker.scrape_audit import record_scrape_audit_event_sync

logger = logging.getLogger(__name__)


def _next_utc(cron_expression: str) -> datetime:
    now = datetime.now(timezone.utc)
    return croniter(cron_expression.strip(), now).get_next(datetime)


def _cron_from_cfg(cfg: Any) -> str | None:
    if not cfg or not isinstance(cfg, dict):
        return None
    st = cfg.get("type") or "cron"
    if st == "hourly":
        return "0 * * * *"
    if st == "daily":
        return "0 0 * * *"
    raw = cfg.get("cron_expression")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def _delay_pair(dmin: float, dmax: float) -> tuple[float, float]:
    if dmax < dmin:
        dmin, dmax = dmax, dmin
    mid = (dmin + dmax) / 2.0
    jitter = max(0.0, (dmax - dmin) / 2.0)
    return mid, jitter


def _crawl_max_pages(crawl_type: str, max_pages: int) -> int:
    ct = (crawl_type or "single_page").strip().lower()
    if ct == "single_page":
        return 1
    return max(1, min(50, int(max_pages)))


@celery_app.task(name="axiom.tick_source_schedules")
def tick_source_schedules() -> dict[str, Any]:
    """Enqueue due source schedules (Celery Beat runs every minute)."""
    dsn = get_psycopg_dsn()
    if not dsn:
        logger.warning("tick_source_schedules.skip_no_database_url")
        return {"processed": 0}

    processed = 0
    with psycopg.connect(dsn, autocommit=False, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, organization_id, created_by_user_id, base_url, crawl_type, allow_external,
                       max_pages, delay_min, delay_max, scrape_engine, include_html, sitemap_url,
                       schedule_config
                FROM sources
                WHERE is_active
                  AND schedule_enabled
                  AND NOT schedule_paused
                  AND next_run_at IS NOT NULL
                  AND next_run_at <= NOW()
                ORDER BY next_run_at ASC
                LIMIT 25
                FOR UPDATE SKIP LOCKED
                """
            )
            rows = cur.fetchall()

        for row in rows:
            try:
                _dispatch_one(conn, row)
                processed += 1
            except Exception:
                conn.rollback()
                logger.exception(
                    "tick_source_schedules.dispatch_failed",
                    extra={"source_id": str(row["id"])},
                )

    logger.info("tick_source_schedules.done", extra={"processed": processed})
    return {"processed": processed}


def _bump_source(conn: psycopg.Connection, source_id: Any, schedule_config: Any) -> None:
    cron_expr = _cron_from_cfg(schedule_config)
    nxt = None
    if cron_expr:
        try:
            nxt = _next_utc(cron_expr)
        except Exception:
            logger.warning(
                "tick_source_schedules.bad_cron",
                extra={"source_id": str(source_id), "cron": cron_expr},
            )
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE sources
            SET last_run_at = NOW(),
                next_run_at = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (nxt, str(source_id)),
        )


def _dispatch_one(conn: psycopg.Connection, row: dict[str, Any]) -> None:
    source_id = row["id"]
    org_id: UUID = row["organization_id"]
    user_id: UUID | None = row["created_by_user_id"]
    schedule_config = row["schedule_config"]
    cron_expr = _cron_from_cfg(schedule_config)
    if not cron_expr:
        logger.warning("tick_source_schedules.skip_no_cron", extra={"source_id": str(source_id)})
        _bump_source(conn, source_id, schedule_config)
        conn.commit()
        return

    if user_id is None:
        logger.warning("tick_source_schedules.skip_no_user", extra={"source_id": str(source_id)})
        _bump_source(conn, source_id, schedule_config)
        conn.commit()
        return

    url_str = str(row.get("base_url") or "").strip()
    if not url_str:
        logger.warning("tick_source_schedules.skip_no_url", extra={"source_id": str(source_id)})
        _bump_source(conn, source_id, schedule_config)
        conn.commit()
        return

    crawl_type = str(row.get("crawl_type") or "single_page")
    max_pages = _crawl_max_pages(crawl_type, int(row.get("max_pages") or 1))
    dmin = float(row.get("delay_min") or 1.5)
    dmax = float(row.get("delay_max") or 2.5)
    delay_s, jitter_s = _delay_pair(dmin, dmax)
    engine = str(row.get("scrape_engine") or "html_requests")
    include_html = bool(row.get("include_html", False))
    allow_ext = bool(row.get("allow_external", False))
    sitemap_url = row.get("sitemap_url")
    sitemap_str = str(sitemap_url).strip() if sitemap_url else None

    correlation_id = uuid.uuid4()
    cid = correlation_id
    settings = ComplianceSettings.from_env()
    ctx = ScrapeComplianceContext(
        user_id=str(user_id),
        organization_id=str(org_id),
        audit_correlation_id=str(correlation_id),
        engine=str(engine),
        source="scheduler",
    )

    try:
        run_compliance_before_fetch(
            url_str,
            ctx=ctx,
            settings=settings,
            preverified=False,
        )
    except ComplianceError as exc:
        record_scrape_audit_event_sync(
            correlation_id=cid,
            source="scheduler",
            user_id=user_id,
            organization_id=org_id,
            url=url_str,
            host=hostname_for_url(url_str) or "invalid",
            engine=str(engine),
            step="compliance",
            outcome="denied",
            error_message=str(exc),
            extra={"source_id": str(source_id)},
        )
        _bump_source(conn, source_id, schedule_config)
        conn.commit()
        return

    job_id = uuid.uuid4()
    run_id = uuid.uuid4()

    job_payload = {
        "url": url_str,
        "engine": engine,
        "include_html": include_html,
        "crawl_type": crawl_type,
        "sitemap_url": sitemap_str,
        "crawl_max_pages": max_pages,
        "crawl_delay_seconds": delay_s,
        "crawl_jitter_seconds": jitter_s,
        "crawl_allow_external": allow_ext,
        "crawl_max_external_pages": 25,
        "crawl_max_external_per_host": 5,
        "pre_fetch_jitter_max_seconds": 0.0,
    }

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO jobs (
                id, organization_id, source_id, kind, status, payload, schedule_id, url, created_at, updated_at
            ) VALUES (
                %s, %s, %s, 'scrape', 'pending', %s::jsonb, NULL, %s, NOW(), NOW()
            )
            """,
            (
                str(job_id),
                str(org_id),
                str(source_id),
                json.dumps(job_payload),
                url_str,
            ),
        )
        cur.execute(
            """
            INSERT INTO runs (id, job_id, status, created_at, updated_at)
            VALUES (%s, %s, 'pending', NOW(), NOW())
            """,
            (str(run_id), str(job_id)),
        )

    async_result = celery_app.send_task(
        "axiom.scrape",
        kwargs={
            "url": url_str,
            "engine": engine,
            "include_html": include_html,
            "user_id": str(user_id),
            "organization_id": str(org_id),
            "audit_correlation_id": str(correlation_id),
            "compliance_preverified": True,
            "job_id": str(job_id),
            "run_id": str(run_id),
            "max_retries_override": 3,
            "crawl_max_pages": max_pages,
            "crawl_delay_seconds": delay_s,
            "crawl_jitter_seconds": jitter_s,
            "crawl_allow_external": allow_ext,
            "crawl_max_external_pages": 25,
            "crawl_max_external_per_host": 5,
            "pre_fetch_jitter_max_seconds": 0.0,
            "crawl_type": crawl_type,
            "sitemap_url": sitemap_str,
        },
        queue=str(celery_app.conf.task_default_queue),
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE jobs SET celery_task_id = %s, status = 'queued', updated_at = NOW() WHERE id = %s
            """,
            (async_result.id, str(job_id)),
        )
        cur.execute(
            """
            UPDATE runs SET status = 'queued', updated_at = NOW() WHERE id = %s
            """,
            (str(run_id),),
        )

    _bump_source(conn, source_id, schedule_config)
    conn.commit()
