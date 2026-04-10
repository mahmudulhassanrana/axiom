"""Load monorepo and worker `.env`, align ``REDIS_URL`` with Celery — before broker config."""

from __future__ import annotations

import os
from pathlib import Path


def load_worker_environment() -> None:
    """
    - Root ``../../..`` from ``axiom_worker`` = repository root (``<repo>/.env``).
    - Worker app dir = ``<repo>/apps/worker/.env`` (overrides).
    - Map ``REDIS_URL`` → ``CELERY_BROKER_URL`` when the latter is unset (matches API / infra).
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    pkg = Path(__file__).resolve().parent
    # axiom_worker -> src -> apps/worker -> apps -> repo
    repo_root = pkg.parents[3]
    worker_root = pkg.parents[1]
    load_dotenv(repo_root / ".env")
    load_dotenv(worker_root / ".env", override=True)

    if not (os.environ.get("CELERY_BROKER_URL") or "").strip():
        red = (os.environ.get("REDIS_URL") or "").strip()
        if red:
            os.environ["CELERY_BROKER_URL"] = red
    if not (os.environ.get("CELERY_RESULT_BACKEND") or "").strip():
        os.environ["CELERY_RESULT_BACKEND"] = os.environ.get(
            "CELERY_BROKER_URL",
            "redis://localhost:6379/0",
        )

    _apply_dev_memory_broker()


def _apply_dev_memory_broker() -> None:
    """Optional single-process dev without Redis (not for production)."""
    flag = (os.environ.get("AXIOM_DEV_MEMORY_BROKER") or "").strip().lower()
    if flag not in {"1", "true", "yes", "on"}:
        return
    os.environ["CELERY_BROKER_URL"] = "memory://"
    os.environ["CELERY_RESULT_BACKEND"] = "rpc://"
