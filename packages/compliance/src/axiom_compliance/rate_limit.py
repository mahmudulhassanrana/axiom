from __future__ import annotations

import logging
import time

from axiom_compliance.exceptions import RateLimitExceededError

logger = logging.getLogger(__name__)


def acquire_per_domain_slot(
    *,
    redis_url: str | None,
    host: str,
    limit: int,
    window_seconds: int,
) -> None:
    """
    Fixed-window counter per domain. If Redis is unavailable, logs a warning and skips
    (single-node deployments should set REDIS_URL for distributed limits).
    """
    if limit <= 0:
        return
    if not redis_url:
        logger.warning(
            "compliance.rate_limit.skipped_no_redis",
            extra={"axiom_audit": True, "host": host},
        )
        return

    import redis as redis_lib

    client = redis_lib.Redis.from_url(redis_url, decode_responses=True)
    try:
        bucket = int(time.time() // max(1, window_seconds))
        key = f"compliance:rl:{host}:{bucket}"
        n = client.incr(key)
        if n == 1:
            client.expire(key, max(1, window_seconds))
        if n > limit:
            client.decr(key)
            raise RateLimitExceededError(
                f"Rate limit exceeded for host {host!r} ({limit} per {window_seconds}s)",
            )
    finally:
        client.close()
