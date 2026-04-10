"""Startup checks and environment-derived security settings (CORS, docs exposure)."""

from __future__ import annotations

import logging
import os

from axiom_api.core.env import is_production

logger = logging.getLogger("axiom_api.security")

# Default dev JWT secret — must not be used in production.
_DEV_JWT_SECRET_FALLBACK = "dev-insecure-jwt-secret-change-me"

# Minimum secret length when ENVIRONMENT indicates production.
_MIN_JWT_SECRET_LEN = 32


def verify_deployment_security() -> None:
    """Fail fast on insecure production configuration."""
    if not is_production():
        return
    key = (os.environ.get("JWT_SECRET_KEY") or "").strip()
    if not key or key == _DEV_JWT_SECRET_FALLBACK:
        msg = "JWT_SECRET_KEY must be set to a strong, non-default value when ENVIRONMENT is production"
        raise RuntimeError(msg)
    if len(key) < _MIN_JWT_SECRET_LEN:
        msg = f"JWT_SECRET_KEY must be at least {_MIN_JWT_SECRET_LEN} characters in production"
        raise RuntimeError(msg)
    logger.info(
        "deployment_security_ok",
        extra={"event": "deployment_security_ok"},
    )


def get_cors_allow_origins() -> list[str]:
    """Comma-separated origins (e.g. ``https://app.example.com,http://localhost:3000``)."""
    raw = (os.environ.get("CORS_ALLOW_ORIGINS") or "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return ["http://localhost:3000"]


def api_docs_exposed() -> bool:
    """In production, OpenAPI UIs and schema are off unless explicitly enabled."""
    if not is_production():
        return True
    v = (os.environ.get("API_DOCS_ENABLED") or "").strip().lower()
    return v in {"1", "true", "yes", "on"}


def max_request_body_bytes() -> int:
    return int(os.environ.get("MAX_REQUEST_BODY_BYTES", str(10 * 1024 * 1024)))


def hsts_enabled() -> bool:
    return (os.environ.get("ENABLE_HSTS") or "").strip().lower() in {"1", "true", "yes", "on"}
