"""Lightweight Celery app for publishing tasks (same broker/backend as workers)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from celery import Celery
from kombu import Queue

AXIOM_QUEUE = "axiom"


def _load_celery_env() -> None:
    """Match worker: monorepo ``.env`` + ``REDIS_URL`` → ``CELERY_BROKER_URL`` when unset."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None  # type: ignore[assignment]
    if load_dotenv:
        pkg = Path(__file__).resolve().parent
        repo_root = pkg.parents[3]
        api_root = pkg.parents[1]
        load_dotenv(repo_root / ".env")
        load_dotenv(api_root / ".env", override=True)
    if not (os.environ.get("CELERY_BROKER_URL") or "").strip():
        red = (os.environ.get("REDIS_URL") or "").strip()
        if red:
            os.environ["CELERY_BROKER_URL"] = red
    if not (os.environ.get("CELERY_RESULT_BACKEND") or "").strip():
        os.environ["CELERY_RESULT_BACKEND"] = os.environ.get(
            "CELERY_BROKER_URL",
            "redis://localhost:6379/0",
        )


@lru_cache(maxsize=1)
def get_celery_app() -> Celery:
    _load_celery_env()
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
        task_queues=(Queue(AXIOM_QUEUE, routing_key=AXIOM_QUEUE),),
        task_default_queue=AXIOM_QUEUE,
        task_default_routing_key=AXIOM_QUEUE,
        task_create_missing_queues=True,
    )
    return app
