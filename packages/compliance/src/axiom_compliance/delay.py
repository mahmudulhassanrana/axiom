from __future__ import annotations

import random
import time


def sleep_delay_with_jitter(*, base_seconds: float, jitter_seconds: float) -> float:
    """
    Sleep for base_seconds + uniform[0, jitter_seconds].
    Returns the actual slept duration (seconds).
    """
    extra = random.uniform(0.0, max(0.0, jitter_seconds))
    total = max(0.0, base_seconds) + extra
    if total > 0:
        time.sleep(total)
    return total
