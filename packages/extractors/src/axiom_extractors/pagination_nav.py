"""Next-page discovery for crawls: HTML rel=next, query ?page= / ?p=, and query synthesis."""

from __future__ import annotations

import logging
import re
from urllib.parse import parse_qsl, urldefrag, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def crawl_visit_key(url: str) -> str:
    """Normalize URL for duplicate detection (host lowercased, path trimmed, no fragment)."""
    u, _ = urldefrag((url or "").strip())
    if not u:
        return ""
    pr = urlparse(u)
    path = pr.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunparse((pr.scheme.lower(), (pr.netloc or "").lower(), path, "", pr.query, ""))


def bump_query_page_param(url: str, param: str) -> str | None:
    """Return URL with ``param`` incremented by 1, or None if param missing or not an int."""
    pr = urlparse(url)
    pairs = parse_qsl(pr.query, keep_blank_values=True)
    out: list[tuple[str, str]] = []
    found = False
    for k, v in pairs:
        if k.lower() == param.lower():
            try:
                n = int(str(v).strip(), 10)
            except ValueError:
                return None
            out.append((k, str(n + 1)))
            found = True
        else:
            out.append((k, v))
    if not found:
        return None
    nq = urlencode(out, doseq=True)
    return urlunparse((pr.scheme, pr.netloc, pr.path, pr.params, nq, ""))


def first_pagination_query_url(url: str) -> str | None:
    """If URL has no ``page`` / ``p`` param, return same path with ``page=2`` (listings)."""
    pr = urlparse(url)
    q = pr.query
    if re.search(r"(^|[?&])(page|p)=", q, re.I):
        return None
    sep = "&" if q else ""
    nq = f"{q}{sep}page=2" if q else "page=2"
    return urlunparse((pr.scheme, pr.netloc, pr.path, pr.params, nq, ""))


def html_next_hrefs(html: str | None, base_url: str) -> list[str]:
    """Collect absolute URLs from ``rel=next`` on ``a`` / ``link`` / ``area``."""
    if not html or not base_url:
        return []
    soup = BeautifulSoup(html, "html.parser")
    found: list[str] = []
    seen: set[str] = set()
    for tag in soup.find_all(["a", "link", "area"]):
        href = tag.get("href")
        if not href:
            continue
        rel = tag.get("rel") or []
        if isinstance(rel, str):
            rel = [rel]
        rel_l = {str(x).lower() for x in rel}
        if "next" not in rel_l:
            continue
        abs_u = urljoin(base_url, str(href).strip())
        u, _ = urldefrag(abs_u)
        if u.startswith(("http://", "https://")) and u not in seen:
            seen.add(u)
            found.append(u)
    return found


def synthetic_next_from_url(current_url: str) -> list[str]:
    """Derive likely next page from ``page`` / ``p`` query or append ``page=2``."""
    out: list[str] = []
    for param in ("page", "p"):
        bumped = bump_query_page_param(current_url, param)
        if bumped and bumped != current_url:
            out.append(bumped)
            break
    else:
        synth = first_pagination_query_url(current_url)
        if synth and crawl_visit_key(synth) != crawl_visit_key(current_url):
            out.append(synth)
    return out


def extra_pagination_targets(
    *,
    html: str | None,
    page_url: str,
    seed_url: str,
) -> list[str]:
    """Ordered candidates: HTML ``rel=next``, then query-based next (deduped by visit key)."""
    base = page_url or seed_url
    ordered: list[str] = []
    keys: set[str] = set()
    cur_key = crawl_visit_key(page_url)

    def push(u: str) -> None:
        k = crawl_visit_key(u)
        if not k or k == cur_key or k in keys:
            return
        keys.add(k)
        ordered.append(u)

    for u in html_next_hrefs(html, base):
        push(u)
    for u in synthetic_next_from_url(page_url):
        push(u)

    if ordered:
        logger.info(
            "pagination_nav.targets",
            extra={"page_url": page_url, "next_count": len(ordered), "first_next": ordered[0]},
        )
    return ordered
