"""Wrap pipeline ``run_compliance_before_fetch`` if ``skip_robots_check`` is unsupported."""

from __future__ import annotations

import inspect
from functools import lru_cache
from typing import Any


@lru_cache(maxsize=1)
def _impl_supports_skip_robots_check() -> bool:
    from axiom_compliance.pipeline import run_compliance_before_fetch as _impl

    return "skip_robots_check" in inspect.signature(_impl).parameters


def run_compliance_before_fetch(
    url: str,
    *,
    ctx: Any,
    settings: Any = None,
    preverified: bool = False,
    skip_robots_check: bool = False,
) -> str:
    from axiom_compliance.pipeline import run_compliance_before_fetch as _impl

    base_kw = {"ctx": ctx, "settings": settings, "preverified": preverified}
    if _impl_supports_skip_robots_check():
        return _impl(url, **base_kw, skip_robots_check=skip_robots_check)
    return _impl(url, **base_kw)
