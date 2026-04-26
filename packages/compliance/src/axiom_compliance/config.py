from __future__ import annotations

import os
from dataclasses import dataclass


def _split_domains(raw: str | None) -> frozenset[str]:
    if not raw or not raw.strip():
        return frozenset()
    parts = []
    for line in raw.split(","):
        h = line.strip().lower().strip(".")
        if h:
            parts.append(h)
    return frozenset(parts)


def _env_bool(key: str, default: bool) -> bool:
    v = os.environ.get(key)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(key: str, default: float) -> float:
    v = os.environ.get(key)
    if v is None or not v.strip():
        return default
    return float(v)


def _env_int(key: str, default: int) -> int:
    v = os.environ.get(key)
    if v is None or not v.strip():
        return default
    return int(v)


@dataclass(frozen=True, slots=True)
class ComplianceSettings:
    """Loaded from environment (call `from_env()` per request/task for fresh values)."""

    enabled: bool
    user_agent: str
    domain_blocklist: frozenset[str]
    domain_allowlist: frozenset[str]
    request_delay_seconds: float
    request_jitter_seconds: float
    rate_limit_per_domain: int
    rate_limit_window_seconds: int
    redis_url: str | None
    robots_timeout_seconds: float
    robots_fail_open: bool
    robots_cache_ttl_seconds: float
    robots_override_enabled: bool

    @classmethod
    def from_env(cls) -> ComplianceSettings:
        redis_url = os.environ.get("COMPLIANCE_REDIS_URL") or os.environ.get("REDIS_URL")
        return cls(
            enabled=_env_bool("COMPLIANCE_ENABLED", True),
            user_agent=os.environ.get(
                "COMPLIANCE_USER_AGENT",
                "AxiomExtractor/0.1 (+https://axiom.local)",
            ).strip(),
            domain_blocklist=_split_domains(os.environ.get("COMPLIANCE_DOMAIN_BLOCKLIST")),
            domain_allowlist=_split_domains(os.environ.get("COMPLIANCE_DOMAIN_ALLOWLIST")),
            request_delay_seconds=_env_float("COMPLIANCE_REQUEST_DELAY_SECONDS", 1.0),
            request_jitter_seconds=_env_float("COMPLIANCE_REQUEST_JITTER_SECONDS", 0.75),
            rate_limit_per_domain=_env_int("COMPLIANCE_RATE_LIMIT_PER_DOMAIN", 30),
            rate_limit_window_seconds=_env_int("COMPLIANCE_RATE_LIMIT_WINDOW_SECONDS", 60),
            redis_url=redis_url.strip() if redis_url and redis_url.strip() else None,
            robots_timeout_seconds=_env_float("COMPLIANCE_ROBOTS_TIMEOUT_SECONDS", 10.0),
            robots_fail_open=_env_bool("COMPLIANCE_ROBOTS_FAIL_OPEN", True),
            robots_cache_ttl_seconds=_env_float("COMPLIANCE_ROBOTS_CACHE_TTL_SECONDS", 3600.0),
            robots_override_enabled=_env_bool("COMPLIANCE_ROBOTS_OVERRIDE_ENABLED", False),
        )
