"""Publish JSON job progress events to Redis for WebSocket fan-out."""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


def _redis_url() -> str | None:
    u = (os.environ.get("REDIS_URL") or os.environ.get("CELERY_BROKER_URL") or "").strip()
    if u.startswith("redis://") or u.startswith("rediss://"):
        return u
    return None


def publish_job_event(job_id: UUID, event: dict[str, Any]) -> None:
    """Best-effort publish to ``axiom:job:{job_id}``; failures are logged only."""
    url = _redis_url()
    if not url or url.startswith("memory://"):
        return
    channel = f"axiom:job:{job_id}"
    try:
        import redis

        r = redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        try:
            r.publish(channel, json.dumps(event, default=str))
        finally:
            r.close()
    except Exception:
        logger.debug("job_events.publish_failed", extra={"job_id": str(job_id)}, exc_info=True)
