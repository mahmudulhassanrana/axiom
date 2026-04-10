from __future__ import annotations

import logging
import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

from axiom_compliance.exceptions import RobotsTxtDisallowedError, RobotsTxtUnavailableError

logger = logging.getLogger(__name__)

_robots_cache: dict[str, tuple[float, RobotFileParser | None, bool]] = {}
"""netloc -> (expires_at, parser_or_none, fail_open_allow_all)"""


def _cache_get(netloc: str, ttl: float) -> tuple[RobotFileParser | None, bool] | None:
    row = _robots_cache.get(netloc)
    if row is None:
        return None
    expires_at, _, _ = row
    if time.time() > expires_at:
        del _robots_cache[netloc]
        return None
    _, parser, allow_all = row
    return (parser, allow_all)


def _cache_set(
    netloc: str,
    ttl: float,
    *,
    parser: RobotFileParser | None,
    allow_all: bool,
) -> None:
    _robots_cache[netloc] = (time.time() + ttl, parser, allow_all)


def assert_robots_allow_fetch(
    url: str,
    *,
    user_agent: str,
    timeout: float,
    fail_open: bool,
    cache_ttl: float,
) -> None:
    parsed = urlparse(url)
    netloc = (parsed.netloc or "").lower()
    if not netloc:
        msg = "URL has no netloc for robots check"
        raise RobotsTxtDisallowedError(msg)

    cached = _cache_get(netloc, cache_ttl)
    if cached is not None:
        parser, allow_all = cached
        if allow_all:
            return
        if parser is not None and parser.can_fetch(user_agent, url):
            return
        raise RobotsTxtDisallowedError(f"robots.txt disallows {url!r} for user-agent")

    robots_url = urljoin(f"{parsed.scheme}://{netloc}/", "robots.txt")
    try:
        resp = requests.get(
            robots_url,
            timeout=timeout,
            headers={"User-Agent": user_agent},
        )
    except requests.RequestException as exc:
        if fail_open:
            logger.warning(
                "compliance.robots.fetch_failed_fail_open",
                extra={"axiom_audit": True, "robots_url": robots_url, "error": str(exc)},
            )
            _cache_set(netloc, cache_ttl, parser=None, allow_all=True)
            return
        raise RobotsTxtUnavailableError(f"Could not fetch robots.txt: {exc}") from exc

    if resp.status_code == 404:
        rp = RobotFileParser()
        rp.parse([])
        _cache_set(netloc, cache_ttl, parser=rp, allow_all=False)
        return

    if resp.status_code >= 400:
        if fail_open:
            logger.warning(
                "compliance.robots.http_error_fail_open",
                extra={
                    "axiom_audit": True,
                    "robots_url": robots_url,
                    "status": resp.status_code,
                },
            )
            _cache_set(netloc, cache_ttl, parser=None, allow_all=True)
            return
        raise RobotsTxtUnavailableError(
            f"robots.txt HTTP {resp.status_code} for {robots_url}",
        )

    rp = RobotFileParser()
    rp.parse(resp.text.splitlines())
    _cache_set(netloc, cache_ttl, parser=rp, allow_all=False)
    if not rp.can_fetch(user_agent, url):
        raise RobotsTxtDisallowedError(f"robots.txt disallows {url!r} for user-agent")
