"""Shared password strength rules for registration and admin-created users."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator, Field


def _validate_password_strength(v: str) -> str:
    if not re.search(r"[a-z]", v):
        msg = "Password must contain a lowercase letter"
        raise ValueError(msg)
    if not re.search(r"[A-Z]", v):
        msg = "Password must contain an uppercase letter"
        raise ValueError(msg)
    if not re.search(r"\d", v):
        msg = "Password must contain a digit"
        raise ValueError(msg)
    return v


StrongPassword = Annotated[
    str,
    Field(min_length=12, max_length=128),
    AfterValidator(_validate_password_strength),
]
