from __future__ import annotations

import logging
import uuid
from uuid import UUID

from axiom_api.db.models.scrape_audit_event import ScrapeAuditEvent
from axiom_api.types.json import JSONValue
from axiom_api.db.session import async_session_factory

logger = logging.getLogger(__name__)


async def record_scrape_audit_event(
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
    extra: dict[str, JSONValue] | None = None,
) -> None:
    """Persist one audit row in its own transaction (survives request rollback on errors)."""
    try:
        factory = async_session_factory()
        async with factory() as session:
            session.add(
                ScrapeAuditEvent(
                    id=uuid.uuid4(),
                    correlation_id=correlation_id,
                    source=source,
                    user_id=user_id,
                    organization_id=organization_id,
                    url=url,
                    host=host,
                    engine=engine,
                    step=step,
                    outcome=outcome,
                    http_status=http_status,
                    error_message=error_message,
                    celery_task_id=celery_task_id,
                    extra=extra,
                )
            )
            await session.commit()
    except Exception:
        logger.exception(
            "scrape_audit.persist_failed",
            extra={
                "correlation_id": str(correlation_id),
                "step": step,
                "outcome": outcome,
            },
        )
