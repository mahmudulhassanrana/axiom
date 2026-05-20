"""Shared URL heuristics for member/profile detail pages."""

from __future__ import annotations

import re

PROFILE_PATH_RE = re.compile(
    r"/(?:member|members|profile|profiles|user|users|person|people|contact|contacts|"
    r"company-profile|company|companies|directory|detail|view|show|staff|team|"
    r"faculty|rep|representative|bio|about)(?:/[^/?#]+)+",
    re.I,
)
# Paginated directory indexes (not individual member/faculty detail pages).
_LIST_INDEX_RE = re.compile(
    r"/(?:teachers|members?|member-list|faculty)(?:/[^/?#]+)*/\d+/?(?:\?.*)?$|/member-list/?$",
    re.I,
)


def is_profile_like_path(href: str) -> bool:
    h = href or ""
    if _LIST_INDEX_RE.search(h):
        return False
    return bool(PROFILE_PATH_RE.search(h))
