"""Resolve page URLs from an XML sitemap or sitemap index (best-effort)."""

from __future__ import annotations

import gzip
import io
import logging
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

import requests

logger = logging.getLogger(__name__)

_NS_RE = re.compile(r"^\{[^}]+\}")


def _strip_ns(tag: str) -> str:
    return _NS_RE.sub("", tag)


def _fetch_body(url: str, timeout: float) -> bytes:
    headers = {"User-Agent": "AxiomWorker/1.0 (+https://example.invalid)"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    raw = resp.content
    if url.endswith(".gz") or (resp.headers.get("Content-Type") or "").lower().find("gzip") >= 0:
        try:
            raw = gzip.decompress(raw)
        except OSError:
            try:
                raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
            except OSError:
                pass
    return raw


def _parse_locs(xml_bytes: bytes, base_url: str, cap: int) -> tuple[list[str], bool]:
    root = ET.fromstring(xml_bytes)
    tag = _strip_ns(root.tag).lower()
    out: list[str] = []
    is_index = tag == "sitemapindex"
    for el in root.iter():
        if _strip_ns(el.tag).lower() != "loc":
            continue
        if el.text:
            u = el.text.strip()
            if u.startswith(("http://", "https://")):
                out.append(u)
            elif u:
                out.append(urljoin(base_url, u))
        if len(out) >= cap:
            break
    return out[:cap], is_index


def resolve_sitemap_seed_urls(sitemap_url: str, max_urls: int, *, timeout: float = 45.0) -> list[str]:
    """Return up to ``max_urls`` http(s) URLs from a sitemap or nested index."""
    max_urls = max(1, min(50, int(max_urls)))
    cap = max_urls * 4
    try:
        body = _fetch_body(sitemap_url, timeout)
    except requests.RequestException as exc:
        logger.warning("sitemap.fetch_failed url=%s err=%s", sitemap_url, exc)
        raise

    locs, is_index = _parse_locs(body, sitemap_url, cap)
    if not is_index:
        return locs[:max_urls]

    merged: list[str] = []
    seen_sub: set[str] = set()
    for sub in locs:
        if len(merged) >= max_urls:
            break
        if sub in seen_sub:
            continue
        seen_sub.add(sub)
        try:
            sub_body = _fetch_body(sub, timeout)
        except requests.RequestException:
            continue
        child_locs, _ = _parse_locs(sub_body, sub, max_urls - len(merged) + 8)
        for u in child_locs:
            if u not in merged:
                merged.append(u)
            if len(merged) >= max_urls:
                break

    return merged[:max_urls]


def default_sitemap_url_for_base(base_url: str) -> str:
    p = urlparse(base_url)
    if not p.scheme or not p.netloc:
        return base_url.rstrip("/") + "/sitemap.xml"
    path = p.path.rstrip("/") or ""
    return f"{p.scheme}://{p.netloc}{path}/sitemap.xml"
