"""Build a normalized profile/member record from a detail page."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

_SOCIAL_RE = re.compile(
    r"https?://(?:www\.)?(linkedin\.com|twitter\.com|x\.com|facebook\.com|instagram\.com|"
    r"youtube\.com|github\.com)/[^\s\"'<>]+",
    re.I,
)


def _first_str(*vals: Any) -> str | None:
    for v in vals:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _social_links_from_html(html: str | None, links: list[dict[str, Any]] | None) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    if html:
        for m in _SOCIAL_RE.finditer(html):
            u = m.group(0).rstrip(".,)")
            if u not in seen:
                seen.add(u)
                found.append(u)
    if links:
        for ln in links:
            href = str(ln.get("href") or "")
            if _SOCIAL_RE.search(href) and href not in seen:
                seen.add(href)
                found.append(href)
    return found[:20]


def build_profile_record(
    *,
    detail_url: str,
    parent_url: str | None,
    title: str | None,
    text: str | None,
    html: str | None,
    structured_entities: dict[str, Any],
    images: list[dict[str, Any]] | None,
    links: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Single member/profile row for ``metadata.member_records``."""
    ents = structured_entities if isinstance(structured_entities, dict) else {}
    names = ents.get("names") if isinstance(ents.get("names"), list) else []
    emails = ents.get("emails") if isinstance(ents.get("emails"), list) else []
    phones = ents.get("phones") if isinstance(ents.get("phones"), list) else []
    addresses = ents.get("addresses") if isinstance(ents.get("addresses"), list) else []

    designation: str | None = None
    company: str | None = None
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for sel in (
            "[class*='designation']",
            "[class*='title']",
            "[class*='role']",
            "[class*='position']",
            ".job-title",
        ):
            el = soup.select_one(sel)
            if el:
                t = el.get_text(separator=" ", strip=True)
                if t and len(t) < 120:
                    designation = t
                    break
        for sel in ("[class*='company']", "[class*='organization']", ".org-name"):
            el = soup.select_one(sel)
            if el:
                t = el.get_text(separator=" ", strip=True)
                if t and len(t) < 200:
                    company = t
                    break

    website: str | None = None
    if links:
        for ln in links:
            href = str(ln.get("href") or "")
            if href.startswith(("http://", "https://")):
                host = (urlparse(href).netloc or "").lower()
                if host and host not in ("linkedin.com", "www.linkedin.com", "facebook.com", "twitter.com"):
                    if not _SOCIAL_RE.search(href):
                        website = href
                        break

    name = _first_str(title, names[0] if names else None)
    return {
        "name": name,
        "company": company,
        "designation": designation,
        "address": addresses[0] if addresses else None,
        "phone": phones[0] if phones else None,
        "email": emails[0] if emails else None,
        "website": website,
        "social_links": _social_links_from_html(html, links),
        "parent_list_url": parent_url,
        "detail_page_url": detail_url,
        "source_url": detail_url,
        "images": images[:12] if images else [],
        "text_excerpt": (text or "")[:4000] if text else None,
    }
