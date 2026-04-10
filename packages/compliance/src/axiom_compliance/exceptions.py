from __future__ import annotations


class ComplianceError(Exception):
    """Base class for policy violations before or during a scrape."""


class DomainBlockedError(ComplianceError):
    """Host matched the blocklist."""


class DomainNotAllowedError(ComplianceError):
    """Allowlist is non-empty and host did not match."""


class RobotsTxtDisallowedError(ComplianceError):
    """robots.txt disallows this URL for our user-agent."""


class RobotsTxtUnavailableError(ComplianceError):
    """robots.txt could not be fetched and strict mode is enabled."""


class RateLimitExceededError(ComplianceError):
    """Per-domain rate limit (Redis) exceeded."""
