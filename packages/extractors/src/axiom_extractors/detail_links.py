"""Extract profile / member detail URLs from list and directory pages."""

from __future__ import annotations

import logging
import os
import re
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

from axiom_extractors.models import ExtractedLink
from axiom_extractors.pagination_nav import crawl_visit_key
from axiom_extractors.profile_paths import is_profile_like_path

logger = logging.getLogger(__name__)
_SKIP_PATH = re.compile(
    r"(login|logout|signin|signup|register|cart|checkout|privacy|terms|#|\.pdf|\.zip|"
    r"javascript:|mailto:|tel:|/content/|event-details|/service/|/news/|member-registration|"
    r"memberregistration|member-login|departed-members|photo-gallery|video-gallery|"
    r"whats-new|digitalshop|/b2b(?:/|\?|$)|play\.google\.com|linkedin\.com)",
    re.I,
)
_SKIP_TEXT = re.compile(r"^(next|prev|previous|back|home|more|»|←|→)$", re.I)


def _max_detail_per_list() -> int:
    raw = (os.environ.get("AXIOM_MAX_DETAIL_PAGES_PER_LIST") or "25").strip()
    try:
        n = int(raw, 10)
    except ValueError:
        n = 25
    return max(1, min(50, n))


def _score_detail_href(href: str, text: str | None, list_key: str) -> int:
    h = (href or "").lower()
    if _SKIP_PATH.search(h):
        return -100
    t = (text or "").strip()
    if t and _SKIP_TEXT.match(t):
        return -50
    score = 0
    if is_profile_like_path(h):
        score += 40
    if re.search(r"/company-profile/", h, re.I):
        score += 35
    if re.search(r"/profile/", h, re.I):
        score += 25
    if re.search(r"/\d{3,}", h):
        score += 15
    if re.search(r"[-_][a-z0-9]{4,}", h, re.I):
        score += 8
    if t and 2 <= len(t) <= 80 and not _SKIP_TEXT.match(t):
        score += 12
    if crawl_visit_key(href) == list_key:
        return -100
    return score


def extract_detail_links(
    *,
    html: str | None,
    page_url: str,
    seed_url: str,
    links: list[ExtractedLink] | None = None,
) -> list[str]:
    """Return absolute detail URLs to crawl (same-site), highest confidence first."""
    base = page_url or seed_url
    list_key = crawl_visit_key(base)
    candidates: list[tuple[int, str]] = []
    seen: set[str] = set()

    def add(href: str, text: str | None) -> None:
        if not href:
            return
        abs_u, _ = urldefrag(urljoin(base, href.strip()))
        if not abs_u.startswith(("http://", "https://")):
            return
        try:
            if (urlparse(abs_u).netloc or "").lower() != (urlparse(seed_url).netloc or "").lower():
                return
        except Exception:
            return
        vk = crawl_visit_key(abs_u)
        if not vk or vk == list_key or vk in seen:
            return
        sc = _score_detail_href(abs_u, text, list_key)
        if sc < 5:
            return
        seen.add(vk)
        candidates.append((sc, abs_u))

    if links:
        for link in links:
            add(link.href, link.text)

    if html:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            add(str(a.get("href", "")), a.get_text(separator=" ", strip=True) or None)
        for row in soup.select("table tbody tr"):
            for a in row.find_all("a", href=True):
                add(str(a.get("href", "")), a.get_text(separator=" ", strip=True) or None)

    candidates.sort(key=lambda x: (-x[0], x[1]))
    cap = _max_detail_per_list()
    out = [u for _, u in candidates[:cap]]
    if out:
        logger.info(
            "detail_links.extracted",
            extra={"list_url": base, "count": len(out), "sample": out[0]},
        )
    return out
