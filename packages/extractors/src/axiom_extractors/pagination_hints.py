"""Prioritize likely pagination / \"next\" URLs when enqueueing crawl candidates."""

from __future__ import annotations

import re

from axiom_extractors.models import ExtractedLink

_PAGE_PARAM_RE = re.compile(r"[?&]page=\d+", re.I)
_PAGE_PATH_RE = re.compile(r"/page/\d+/?$", re.I)


def pagination_priority(href: str, text: str | None) -> int:
    """
    Higher score = enqueue first. 0 = normal internal link.
    """
    h = (href or "").lower()
    t = (text or "").strip().lower()
    score = 0
    if t in (
        "next",
        "next page",
        "next »",
        "older posts",
        "newer posts",
        "load more",
        "show more",
        "»",
        "→",
        "siguiente",
        "suivant",
    ):
        score += 50
    if "rel=next" in h:  # rare in href
        score += 40
    if _PAGE_PARAM_RE.search(h) or _PAGE_PATH_RE.search(h):
        score += 30
    if re.search(r"[?&]p=\d+", h, re.I):
        score += 25
    if "offset=" in h or "start=" in h or "cursor=" in h:
        score += 15
    return score


def sort_links_for_crawl(links: list[ExtractedLink]) -> list[ExtractedLink]:
    """Stable sort: high pagination hints first."""
    scored: list[tuple[int, int, ExtractedLink]] = []
    for i, link in enumerate(links):
        pr = pagination_priority(link.href, link.text)
        scored.append((-pr, i, link))
    scored.sort(key=lambda x: (x[0], x[1]))
    return [x[2] for x in scored]
