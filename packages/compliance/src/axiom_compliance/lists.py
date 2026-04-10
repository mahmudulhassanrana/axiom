from __future__ import annotations

from urllib.parse import urlparse

from axiom_compliance.exceptions import DomainBlockedError, DomainNotAllowedError


def hostname_for_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().strip()
    return host


def host_matches_list(host: str, patterns: frozenset[str]) -> bool:
    """True if host equals a pattern or is a subdomain of it (suffix match)."""
    for p in patterns:
        if host == p:
            return True
        if host.endswith("." + p):
            return True
    return False


def enforce_domain_lists(url: str, *, blocklist: frozenset[str], allowlist: frozenset[str]) -> str:
    host = hostname_for_url(url)
    if not host:
        msg = "URL has no hostname"
        raise DomainBlockedError(msg)
    if blocklist and host_matches_list(host, blocklist):
        raise DomainBlockedError(f"Host {host!r} is blocklisted")
    if allowlist and not host_matches_list(host, allowlist):
        raise DomainNotAllowedError(f"Host {host!r} is not on the allowlist")
    return host
