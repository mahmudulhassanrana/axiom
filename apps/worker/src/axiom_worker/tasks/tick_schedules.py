from __future__ import annotations

import json
import logging
import os
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
from axiom_worker.scrape_audit import record_scrape_audit_event_sync

logger = logging.getLogger(__name__)


def _dsn() -> str | None:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return None
    if "+asyncpg" in url:
        return url.replace("postgresql+asyncpg", "postgresql", 1)
    return url


def _next_utc(cron_expression: str) -> datetime:
    now = datetime.now(timezone.utc)
    return croniter(cron_expression.strip(), now).get_next(datetime)


@celery_app.task(name="axiom.tick_schedules")
def tick_schedules() -> dict[str, Any]:
    """
    Enqueue due cron schedules (Celery Beat should run this every minute).

    Creates a Job + Run per schedule tick and dispatches ``axiom.scrape``.
    """
    dsn = _dsn()
    if not dsn:
        logger.warning("tick_schedules.skip_no_database_url")
        return {"processed": 0}

    processed = 0
    with psycopg.connect(dsn, autocommit=False, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, organization_id, created_by_user_id, cron_expression, payload, max_retries
                FROM job_schedules
                WHERE NOT paused
                  AND next_run_at IS NOT NULL
                  AND next_run_at <= NOW()
                ORDER BY next_run_at ASC
                LIMIT 50
                FOR UPDATE SKIP LOCKED
                """
            )
            rows = cur.fetchall()

        for row in rows:
            try:
                # One row failure must not abort the batch or poison the connection (savepoint).
                with conn.transaction():
                    _dispatch_one(conn, row)
                processed += 1
            except Exception:
                logger.exception(
                    "tick_schedules.dispatch_failed",
                    extra={"schedule_id": str(row["id"])},
                )
        conn.commit()

    logger.info("tick_schedules.done", extra={"processed": processed})
    return {"processed": processed}


def _dispatch_one(conn: psycopg.Connection, row: dict[str, Any]) -> None:
    schedule_id = row["id"]
    org_id: UUID = row["organization_id"]
    user_id: UUID | None = row["created_by_user_id"]
    cron_expression: str = row["cron_expression"]
    payload: dict[str, Any] = dict(row["payload"])
    max_retries: int = int(row["max_retries"])

    if user_id is None:
        logger.warning("tick_schedules.skip_no_user", extra={"schedule_id": str(schedule_id)})
        _bump_schedule(conn, schedule_id, cron_expression)
        return

    url_str = str(payload.get("url") or "")
    if not url_str:
        logger.warning("tick_schedules.skip_no_url", extra={"schedule_id": str(schedule_id)})
        _bump_schedule(conn, schedule_id, cron_expression)
        return

    engine = payload.get("engine") or "html_requests"
    include_html = bool(payload.get("include_html", False))
    raw_source = payload.get("source_id")
    source_id: str | None = str(raw_source) if raw_source else None

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
            extra={"schedule_id": str(schedule_id)},
        )
        _bump_schedule(conn, schedule_id, cron_expression)
        return

    job_id = uuid.uuid4()
    run_id = uuid.uuid4()

    job_payload = {
        "url": url_str,
        "engine": engine,
        "include_html": include_html,
        "source_id": source_id,
        "schedule_id": str(schedule_id),
    }

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO jobs (
                id, organization_id, source_id, kind, status, payload, schedule_id, url, created_at, updated_at
            ) VALUES (
                %s, %s, %s, 'scrape', 'pending', %s::jsonb, %s, %s, NOW(), NOW()
            )
            """,
            (
                str(job_id),
                str(org_id),
                source_id,
                json.dumps(job_payload),
                str(schedule_id),
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
            "schedule_id": str(schedule_id),
            "max_retries_override": max_retries,
        },
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

    _bump_schedule(conn, schedule_id, cron_expression)


def _bump_schedule(conn: psycopg.Connection, schedule_id: Any, cron_expression: str) -> None:
    nxt = _next_utc(cron_expression)
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE job_schedules
            SET last_run_at = NOW(),
                next_run_at = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (nxt, str(schedule_id)),
        )
