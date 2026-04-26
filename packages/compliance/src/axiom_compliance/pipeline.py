from __future__ import annotations

from dataclasses import dataclass

from axiom_compliance.audit import log_scrape_audit
from axiom_compliance.config import ComplianceSettings
from axiom_compliance.delay import sleep_delay_with_jitter
from axiom_compliance.lists import enforce_domain_lists, hostname_for_url
from axiom_compliance.rate_limit import acquire_per_domain_slot
from axiom_compliance.robots import assert_robots_allow_fetch


@dataclass(frozen=True, slots=True)
class ScrapeComplianceContext:
    """Correlation and identity for audit logs (and optional DB rows elsewhere)."""

    user_id: str | None = None
    organization_id: str | None = None
    audit_correlation_id: str | None = None
    celery_task_id: str | None = None
    engine: str = "html_requests"
    source: str = "api"


def _base_audit(ctx: ScrapeComplianceContext, url: str, host: str) -> dict:
    return {
        "url": url,
        "host": host,
        "engine": ctx.engine,
        "source": ctx.source,
        "user_id": ctx.user_id,
        "organization_id": ctx.organization_id,
        "audit_correlation_id": ctx.audit_correlation_id,
        "celery_task_id": ctx.celery_task_id,
    }


def run_compliance_before_fetch(
    url: str,
    *,
    ctx: ScrapeComplianceContext,
    settings: ComplianceSettings | None = None,
    preverified: bool = False,
    skip_robots_check: bool = False,
) -> str:
    """
    Enforce lists, Redis per-domain rate limit, delay+jitter, and robots.txt.
    Returns the normalized hostname. Raises ComplianceError subclasses on violation.
    """
    cfg = settings or ComplianceSettings.from_env()
    if not cfg.enabled:
        h = hostname_for_url(url)
        log_scrape_audit("compliance.disabled", **_base_audit(ctx, url, h))
        return h

    if preverified:
        h = hostname_for_url(url)
        log_scrape_audit("compliance.preverified_skip", **_base_audit(ctx, url, h))
        return h

    host = enforce_domain_lists(
        url,
        blocklist=cfg.domain_blocklist,
        allowlist=cfg.domain_allowlist,
    )

    log_scrape_audit(
        "compliance.step",
        step="domain_lists",
        outcome="ok",
        **_base_audit(ctx, url, host),
    )

    acquire_per_domain_slot(
        redis_url=cfg.redis_url,
        host=host,
        limit=cfg.rate_limit_per_domain,
        window_seconds=cfg.rate_limit_window_seconds,
    )
    log_scrape_audit(
        "compliance.step",
        step="rate_limit",
        outcome="ok",
        **_base_audit(ctx, url, host),
    )

    slept = sleep_delay_with_jitter(
        base_seconds=cfg.request_delay_seconds,
        jitter_seconds=cfg.request_jitter_seconds,
    )
    log_scrape_audit(
        "compliance.step",
        step="delay",
        outcome="ok",
        delay_seconds=slept,
        **_base_audit(ctx, url, host),
    )

    allow_skip = bool(skip_robots_check and cfg.robots_override_enabled)
    if allow_skip:
        log_scrape_audit(
            "compliance.robots_skipped_override",
            step="robots",
            outcome="override",
            **_base_audit(ctx, url, host),
        )
    else:
        assert_robots_allow_fetch(
            url,
            user_agent=cfg.user_agent,
            timeout=cfg.robots_timeout_seconds,
            fail_open=cfg.robots_fail_open,
            cache_ttl=cfg.robots_cache_ttl_seconds,
        )
        log_scrape_audit(
            "compliance.step",
            step="robots",
            outcome="ok",
            **_base_audit(ctx, url, host),
        )

    log_scrape_audit("compliance.passed", **_base_audit(ctx, url, host))
    return host
