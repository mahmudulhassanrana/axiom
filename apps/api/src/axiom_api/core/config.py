from __future__ import annotations

import os
from functools import lru_cache


def get_jwt_secret_key() -> str:
    key = os.environ.get("JWT_SECRET_KEY", "")
    if not key:
        return "dev-insecure-jwt-secret-change-me"
    return key


def get_api_key_pepper() -> str:
    """Appended before hashing API keys (defense in depth)."""
    return os.environ.get("API_KEY_PEPPER") or get_jwt_secret_key()


def get_access_token_expire_minutes() -> int:
    return int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))


def get_auto_create_schema() -> bool:
    v = os.environ.get("AXIOM_AUTO_CREATE_SCHEMA", "true").strip().lower()
    return v in ("1", "true", "yes", "on")


def get_seed_default_admin() -> bool:
    v = os.environ.get("AXIOM_SEED_DEFAULT_ADMIN", "true").strip().lower()
    return v in ("1", "true", "yes", "on")


def get_jwt_issuer() -> str:
    """``iss`` claim for access tokens (validate on decode)."""
    return (os.environ.get("JWT_ISSUER") or "axiom").strip()


def get_jwt_audience() -> str:
    """``aud`` claim for access tokens (validate on decode)."""
    return (os.environ.get("JWT_AUDIENCE") or "axiom-api").strip()


@lru_cache(maxsize=1)
def get_database_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://axiom:axiom@localhost:5432/axiom",
    )


def get_sync_database_url() -> str:
    """Alembic / sync tooling (psycopg v3)."""
    url = get_database_url()
    if "+asyncpg" in url:
        return url.replace("postgresql+asyncpg", "postgresql+psycopg", 1)
    return url
