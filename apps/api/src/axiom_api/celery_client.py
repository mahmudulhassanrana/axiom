"""Lightweight Celery app for publishing tasks (same broker/backend as workers)."""

from __future__ import annotations

import os
from functools import lru_cache

from celery import Celery


@lru_cache(maxsize=1)
def get_celery_app() -> Celery:
    broker = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    backend = os.environ.get("CELERY_RESULT_BACKEND", broker)
    app = Celery("axiom", broker=broker, backend=backend)
    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        # Must match `axiom_worker.celery_app` so workers consume published tasks.
        task_default_queue="axiom",
    )
    return app
