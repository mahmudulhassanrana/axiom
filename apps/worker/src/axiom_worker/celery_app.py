import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init
from kombu import Queue

from axiom_worker.env import load_worker_environment

load_worker_environment()


@worker_process_init.connect
def _load_env_in_worker_process(**_kwargs: object) -> None:
    """Ensure prefork pool children load the same ``.env`` chain as the parent (``DATABASE_URL``, etc.)."""
    load_worker_environment()

_broker = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
_backend = os.environ.get("CELERY_RESULT_BACKEND", _broker)

AXIOM_QUEUE = "axiom"

app = Celery(
    "axiom",
    broker=_broker,
    backend=_backend,
    include=["axiom_worker.tasks"],
)

app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    result_expires=86400,
    task_queues=(Queue(AXIOM_QUEUE, routing_key=AXIOM_QUEUE),),
    task_default_queue=AXIOM_QUEUE,
    task_default_routing_key=AXIOM_QUEUE,
    task_create_missing_queues=True,
    # Sensible defaults for network-heavy tasks (override per-task where needed).
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "tick-cron-job-schedules": {
            "task": "axiom.tick_schedules",
            "schedule": crontab(minute="*"),
        },
        "tick-source-schedules": {
            "task": "axiom.tick_source_schedules",
            "schedule": crontab(minute="*"),
        },
    },
)
