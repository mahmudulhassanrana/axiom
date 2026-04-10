"""
Celery entry for: ``celery -A worker worker --loglevel=info`` (run from ``apps/worker``).

Adds ``src`` to ``sys.path`` so ``axiom_worker`` resolves without ``pip install -e``.
Fails fast if Redis is unreachable instead of Celery retrying 100 times.

Broker env is loaded in ``axiom_worker.celery_app`` via ``load_worker_environment``; we only
run Redis ping here before Celery imports the app.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_REPO = _ROOT.parent.parent

_SRC = _ROOT / "src"

if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from axiom_worker.env import (  # noqa: E402
    ensure_database_url_from_env_files,
    load_worker_environment,
)

ensure_database_url_from_env_files()

try:
    from dotenv import load_dotenv

    for _env_path in (
        _REPO / ".env",
        _REPO / "apps" / "api" / ".env",
        _ROOT / ".env",
    ):
        if _env_path.is_file():
            load_dotenv(_env_path, override=True)
except ImportError:
    pass

load_worker_environment()


def _repo_root() -> Path:
    return _ROOT.parent.parent


def _try_auto_start_redis(url: str) -> bool:
    """Run ``run-redis.sh`` if Redis is down. Opt out: ``AXIOM_AUTO_START_REDIS=0``."""
    auto = (os.environ.get("AXIOM_AUTO_START_REDIS") or "").strip().lower()
    if auto in {"0", "false", "no", "off"}:
        return False
    if not url.startswith("redis://") and not url.startswith("rediss://"):
        return False
    script = _repo_root() / "scripts" / "run-redis.sh"
    if not script.is_file():
        return False
    try:
        subprocess.run([str(script)], cwd=str(_repo_root()), timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    import redis

    for _ in range(10):
        time.sleep(1)
        try:
            redis.from_url(url, socket_connect_timeout=2, socket_timeout=2).ping()
            print("worker: Redis is up (started via scripts/run-redis.sh).", file=sys.stderr)
            return True
        except Exception:
            continue
    return False


def _redis_preflight() -> None:
    if (os.environ.get("SKIP_REDIS_PREFLIGHT") or "").strip().lower() in {"1", "true", "yes", "on"}:
        return
    url = (os.environ.get("CELERY_BROKER_URL") or "").strip() or "redis://localhost:6379/0"
    if url.startswith("memory://"):
        return
    try:
        import redis

        r = redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        r.ping()
    except Exception as first_exc:
        if _try_auto_start_redis(url):
            try:
                redis.from_url(url, socket_connect_timeout=2, socket_timeout=2).ping()
                return
            except Exception as retry_exc:
                err = retry_exc
        else:
            err = first_exc
        print(
            f"ERROR: Cannot reach Redis at {url!r} ({err}).\n"
            "\n"
            "Start Redis, then run Celery again. Examples:\n"
            "  From repository root:  ./scripts/run-redis.sh\n"
            "  Or:                     ./scripts/run-worker.sh\n"
            "  Docker:                 docker compose -f infra/docker-compose.yml up -d redis\n"
            "  macOS (Homebrew):       brew install redis && brew services start redis\n"
            "  No Redis (dev only):    AXIOM_DEV_MEMORY_BROKER=1 in .env\n"
            "\n"
            "Check:  redis-cli -u redis://127.0.0.1:6379 ping   # expect PONG\n",
            file=sys.stderr,
        )
        raise SystemExit(1) from err


_redis_preflight()

from axiom_worker.celery_app import app  # noqa: E402

__all__ = ["app"]
