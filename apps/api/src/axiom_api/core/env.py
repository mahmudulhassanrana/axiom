from __future__ import annotations

import os


def is_production() -> bool:
    v = (os.environ.get("ENVIRONMENT") or os.environ.get("AXIOM_ENV") or "").strip().lower()
    return v in {"production", "prod"}
