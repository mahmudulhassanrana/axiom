"""Safe human-like pacing for browser extraction (no evasion / stealth)."""

from __future__ import annotations

import random
import time
from typing import Any


def human_delay_seconds(*, min_s: float = 1.0, max_s: float = 4.0) -> float:
    return random.uniform(min_s, max_s)


def sleep_human_delay(*, min_s: float = 1.0, max_s: float = 4.0) -> None:
    time.sleep(human_delay_seconds(min_s=min_s, max_s=max_s))


def gradual_scroll(page: Any, *, steps: int = 6) -> None:
    """Scroll down the page in steps so lazy content can render."""
    try:
        for i in range(max(1, steps)):
            page.evaluate(
                """(step, total) => {
                    const h = document.body ? document.body.scrollHeight : 0;
                    window.scrollTo(0, Math.min(h, (h / total) * (step + 1)));
                }""",
                i,
                steps,
            )
            page.wait_for_timeout(random.randint(180, 520))
    except Exception:
        return
