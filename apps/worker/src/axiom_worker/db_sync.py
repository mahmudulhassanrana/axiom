"""Sync PostgreSQL URL for worker-side ``psycopg`` — same logical DB as the API ``DATABASE_URL``."""

from __future__ import annotations

import os

from axiom_worker.env import (
    ensure_database_url_from_env_files,
    load_worker_environment,
    resolve_repo_root,
)


def normalize_postgres_url_for_psycopg(url: str) -> str:
    """
    Convert SQLAlchemy-style URLs to a form ``psycopg.connect`` accepts.

    Mirrors ``axiom_api.core.config.get_sync_database_url`` so API (async SQLAlchemy)
    and worker (sync psycopg) target the same database.
    """
    u = url.strip()
    if "+asyncpg" in u:
        u = u.replace("postgresql+asyncpg", "postgresql", 1)
    if "+psycopg" in u:
        u = u.replace("postgresql+psycopg", "postgresql", 1)
    if "+psycopg2" in u:
        u = u.replace("postgresql+psycopg2", "postgresql", 1)
    return u


def _database_url_from_dotenv_files() -> str:
    """Read ``DATABASE_URL`` from disk when the process env is empty (e.g. Celery pool quirks)."""
    try:
        from dotenv import dotenv_values
    except ImportError:
        return ""
    repo = resolve_repo_root()
    url = ""
    for path in (
        repo / ".env",
        repo / "apps" / "api" / ".env",
        repo / "apps" / "worker" / ".env",
    ):
        if not path.is_file():
            continue
        vals = dotenv_values(path)
        v = vals.get("DATABASE_URL")
        if v is not None and str(v).strip():
            url = str(v).strip()
    if url:
        os.environ["DATABASE_URL"] = url
    return url


def get_psycopg_dsn() -> str | None:
    """``DATABASE_URL`` from env (after worker dotenv load), or ``None`` if unset."""
    ensure_database_url_from_env_files()
    load_worker_environment()
    raw = (os.environ.get("DATABASE_URL") or "").strip()
    if not raw:
        raw = _database_url_from_dotenv_files().strip()
    if not raw:
        return None
    return normalize_postgres_url_for_psycopg(raw)
