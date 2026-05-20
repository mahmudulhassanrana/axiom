"""Heuristic page-type detection for crawl routing."""

from __future__ import annotations

import re
from typing import Any, Literal

from bs4 import BeautifulSoup

from axiom_extractors.models import ExtractedLink
from axiom_extractors.profile_paths import is_profile_like_path

PageType = Literal["list", "profile", "article", "pagination", "unknown"]
_PAGINATION_PATH = re.compile(r"[?&](page|p)=\d+", re.I)


def detect_page_type(
    *,
    url: str,
    html: str | None,
    links: list[ExtractedLink],
    metadata: dict[str, Any] | None = None,
) -> PageType:
    if is_profile_like_path(url):
        return "profile"

    meta = metadata if isinstance(metadata, dict) else {}
    if meta.get("member_records") and isinstance(meta.get("member_records"), list):
        if len(meta["member_records"]) >= 2:
            return "list"

    if _PAGINATION_PATH.search(url) and html and len((html or "")) < 80_000:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True).lower()
        if "next" in text and len(links) < 40:
            return "pagination"

    if not html:
        return "unknown"

    soup = BeautifulSoup(html, "html.parser")
    profile_hits = sum(1 for a in soup.find_all("a", href=True) if is_profile_like_path(str(a.get("href", ""))))
    cards = len(
        soup.select(
            "[class*='member'], [class*='profile'], [class*='card'], "
            "table tbody tr, .listing-item, [class*='directory']"
        )
    )
    tables = len(soup.find_all("table"))
    article = soup.find("article") is not None
    h1_count = len(soup.find_all("h1"))
    plain_len = len(soup.get_text(separator=" ", strip=True))

    detail_like = sum(1 for link in links if is_profile_like_path(link.href or ""))

    if detail_like >= 5 or (cards >= 6 and profile_hits >= 4) or (tables >= 1 and profile_hits >= 8):
        return "list"

    if profile_hits >= 1 and detail_like <= 2 and h1_count <= 2 and plain_len < 25_000:
        if cards <= 3:
            return "profile"

    if article and plain_len > 1200 and detail_like < 4:
        return "article"

    if detail_like >= 2 and (cards >= 2 or tables >= 1 or profile_hits >= 3):
        return "list"

    if profile_hits >= 3 and detail_like >= 1:
        return "list"

    return "unknown"
