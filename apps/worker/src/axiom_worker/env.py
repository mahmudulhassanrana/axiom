"""Load monorepo and worker `.env`, align ``REDIS_URL`` with Celery — before broker config."""

from __future__ import annotations

import os
from pathlib import Path


def _parse_database_url_line_from_env_file(path: Path) -> str | None:
    """Read ``DATABASE_URL`` from a single ``.env`` file (last assignment wins). No python-dotenv."""
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    found: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        if key.strip() != "DATABASE_URL":
            continue
        v = val.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        if v.strip():
            found = v.strip()
    return found


def _bootstrap_database_url_for_repo(repo_root: Path) -> bool:
    """Set ``DATABASE_URL`` in ``os.environ`` from repo / api / worker ``.env`` if missing."""
    if (os.environ.get("DATABASE_URL") or "").strip():
        return True
    api_root = repo_root / "apps" / "api"
    worker_root = repo_root / "apps" / "worker"
    url = ""
    for path in (repo_root / ".env", api_root / ".env", worker_root / ".env"):
        u = _parse_database_url_line_from_env_file(path)
        if u:
            url = u
    if url:
        os.environ["DATABASE_URL"] = url
        return True
    return False


def _candidate_repo_roots() -> list[Path]:
    """Ordered roots to try for ``.env`` (``AXIOM_REPO_ROOT``, discovery, then src-layout depth)."""
    seen: set[Path] = set()
    out: list[Path] = []

    def add(p: Path) -> None:
        try:
            r = p.resolve()
        except OSError:
            return
        if r in seen:
            return
        seen.add(r)
        out.append(r)

    raw = (os.environ.get("AXIOM_REPO_ROOT") or "").strip()
    if raw:
        add(Path(raw).expanduser())
    pkg = Path(__file__).resolve().parent
    add(_repo_root_from_package(pkg))
    try:
        add(pkg.parents[3])
    except IndexError:
        pass
    return out


def ensure_database_url_from_env_files() -> None:
    """Ensure ``DATABASE_URL`` is set from on-disk ``.env`` when the process env is empty."""
    if (os.environ.get("DATABASE_URL") or "").strip():
        return
    for root in _candidate_repo_roots():
        if _bootstrap_database_url_for_repo(root):
            return


def _repo_root_from_package(pkg_dir: Path) -> Path:
    for base in (pkg_dir, *pkg_dir.parents):
        try:
            if (base / "apps" / "api").is_dir() and (base / "apps" / "worker").is_dir():
                return base
        except OSError:
            continue
    return pkg_dir.parents[3]


def resolve_repo_root() -> Path:
    """Monorepo root (contains ``apps/api`` and ``apps/worker``)."""
    return _repo_root_from_package(Path(__file__).resolve().parent)


def load_worker_environment() -> None:
    """
    Mirror API ``main.py`` dotenv order so ``DATABASE_URL`` matches, then apply worker overrides.

    - ``<repo>/.env``
    - ``<repo>/apps/api/.env`` (override — same as ``uvicorn`` from ``apps/api``)
    - ``<repo>/apps/worker/.env`` (override — Celery-specific vars)

    Celery prefork pool children also call this from ``worker_process_init`` so each process
    reloads from disk (parent env is usually inherited; this covers edge cases).
    """
    ensure_database_url_from_env_files()

    try:
        from dotenv import load_dotenv
    except ImportError:
        _apply_redis_celery_defaults()
        _apply_dev_memory_broker()
        return

    repo_root = resolve_repo_root()
    worker_root = repo_root / "apps" / "worker"
    api_root = repo_root / "apps" / "api"

    for path in (repo_root / ".env", api_root / ".env", worker_root / ".env"):
        if path.is_file():
            load_dotenv(path, override=True)

    _apply_redis_celery_defaults()
    _apply_dev_memory_broker()


def _apply_redis_celery_defaults() -> None:
    if not (os.environ.get("CELERY_BROKER_URL") or "").strip():
        red = (os.environ.get("REDIS_URL") or "").strip()
        if red:
            os.environ["CELERY_BROKER_URL"] = red
    if not (os.environ.get("CELERY_RESULT_BACKEND") or "").strip():
        os.environ["CELERY_RESULT_BACKEND"] = os.environ.get(
            "CELERY_BROKER_URL",
            "redis://localhost:6379/0",
        )


def _apply_dev_memory_broker() -> None:
    """Optional single-process dev without Redis (not for production)."""
    flag = (os.environ.get("AXIOM_DEV_MEMORY_BROKER") or "").strip().lower()
    if flag not in {"1", "true", "yes", "on"}:
        return
    os.environ["CELERY_BROKER_URL"] = "memory://"
    os.environ["CELERY_RESULT_BACKEND"] = "rpc://"
