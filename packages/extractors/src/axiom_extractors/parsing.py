from __future__ import annotations

import hashlib
import json as json_lib
from typing import Any
from urllib.parse import urldefrag, urljoin

from bs4 import BeautifulSoup

from axiom_extractors.models import ExtractedDocument, ExtractedLink, ExtractorKind


def normalize_whitespace(value: str) -> str:
    """Collapse runs of whitespace and blank lines."""
    lines: list[str] = []
    for raw in value.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = " ".join(raw.split())
        if line:
            lines.append(line)
    return "\n".join(lines)


def _strip_noise_tags(soup: BeautifulSoup) -> None:
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()


def visible_text_from_soup(soup: BeautifulSoup) -> str:
    """Plain text from body (or whole tree) with noise tags removed."""
    work = BeautifulSoup(str(soup), "html.parser")
    _strip_noise_tags(work)
    root = work.body if work.body else work
    raw = root.get_text(separator="\n", strip=True)
    return normalize_whitespace(raw)


def _page_title(soup: BeautifulSoup) -> str | None:
    if soup.title and soup.title.string:
        return normalize_whitespace(soup.title.string.strip()) or None
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return normalize_whitespace(str(og["content"]).strip()) or None
    return None


def _meta_tags(soup: BeautifulSoup, *, max_tags: int = 80) -> dict[str, str]:
    """Common ``name`` / ``property`` meta tags (description, og:*, twitter:*, etc.)."""
    out: dict[str, str] = {}
    for m in soup.find_all("meta"):
        if len(out) >= max_tags:
            break
        key = m.get("name") or m.get("property") or m.get("itemprop")
        content = m.get("content")
        if not key or not content:
            continue
        k = str(key).strip()
        v = str(content).strip()
        if not k or not v:
            continue
        out[k] = v[:4000]
    return out


def _json_ld_from_soup(soup: BeautifulSoup, *, max_blocks: int = 24) -> list[dict[str, Any]]:
    """Parse ``application/ld+json`` script blocks (best-effort)."""
    out: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if len(out) >= max_blocks:
            break
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        try:
            data = json_lib.loads(raw)
        except json_lib.JSONDecodeError:
            continue
        if isinstance(data, dict):
            out.append(data)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    out.append(item)
                    if len(out) >= max_blocks:
                        break
    return out


def _html_language(soup: BeautifulSoup) -> str | None:
    html = soup.find("html")
    if not html:
        return None
    lang = html.get("lang") or html.get("xml:lang")
    if not lang:
        return None
    value = str(lang).strip()
    return value or None


def extract_links_from_soup(soup: BeautifulSoup, base_url: str) -> list[ExtractedLink]:
    out: list[ExtractedLink] = []
    seen: set[tuple[str, str | None]] = set()
    for a in soup.find_all("a", href=True):
        href = str(a.get("href", "")).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        absolute = urljoin(base_url, href)
        canonical, _frag = urldefrag(absolute)
        label = a.get_text(separator=" ", strip=True)
        text = normalize_whitespace(label) if label else None
        key = (canonical, text)
        if key in seen:
            continue
        seen.add(key)
        out.append(ExtractedLink(href=canonical, text=text))
    return out


def build_document_from_html(
    *,
    url: str,
    final_url: str | None,
    http_status: int | None,
    html: str,
    extractor_kind: ExtractorKind,
    include_html: bool,
    metadata: dict[str, Any] | None = None,
) -> ExtractedDocument:
    """Parse HTML into a normalized :class:`ExtractedDocument`."""
    soup = BeautifulSoup(html, "html.parser")
    base = final_url or url
    title = _page_title(soup)
    language = _html_language(soup)
    text = visible_text_from_soup(soup)
    links = extract_links_from_soup(soup, base_url=base)
    meta = dict(metadata or {})
    meta.setdefault("meta_tags", _meta_tags(soup))
    jld = _json_ld_from_soup(soup)
    if jld:
        meta.setdefault("structured_data", {})["json_ld"] = jld
    if text:
        meta.setdefault("content_sha256", hashlib.sha256(text.encode("utf-8")).hexdigest())
    return ExtractedDocument(
        url=url,
        final_url=final_url,
        title=title,
        language=language,
        text=text,
        links=links,
        extractor_kind=extractor_kind,
        http_status=http_status,
        metadata=meta,
        html=html if include_html else None,
    )
