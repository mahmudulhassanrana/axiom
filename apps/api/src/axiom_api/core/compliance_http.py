from __future__ import annotations

from fastapi import HTTPException, status

from axiom_compliance import RateLimitExceededError
from axiom_compliance.exceptions import (
    ComplianceError,
    DomainBlockedError,
    DomainNotAllowedError,
    RobotsTxtDisallowedError,
    RobotsTxtUnavailableError,
)


def compliance_http_exception(exc: ComplianceError) -> HTTPException:
    if isinstance(exc, RateLimitExceededError):
        return HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "rate_limit_exceeded",
                "message": "Too many requests to this host for the current window. Retry later.",
            },
        )
    if isinstance(exc, DomainBlockedError):
        return HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={
                "code": "domain_blocked",
                "message": "This host is not allowed by policy.",
            },
        )
    if isinstance(exc, DomainNotAllowedError):
        return HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={
                "code": "domain_not_allowed",
                "message": "This host is not on the allowed list for scraping.",
            },
        )
    if isinstance(exc, RobotsTxtDisallowedError):
        return HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={
                "code": "robots_disallowed",
                "message": "robots.txt disallows fetching this URL for our user agent.",
            },
        )
    if isinstance(exc, RobotsTxtUnavailableError):
        return HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={
                "code": "robots_unavailable",
                "message": "robots.txt could not be evaluated for this host.",
            },
        )
    return HTTPException(
        status.HTTP_403_FORBIDDEN,
        detail={
            "code": "policy_denied",
            "message": "Request blocked by scraping policy.",
        },
    )
