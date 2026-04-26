"""Classify asset URLs and collect image references (no downloads)."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

_IMAGE_EXT = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".avif"})
_DOC_EXT = {
    ".pdf": "pdf",
    ".csv": "csv",
    ".zip": "zip",
    ".json": "json",
    ".xml": "xml",
    ".txt": "text",
    ".xls": "xls",
    ".xlsx": "xlsx",
    ".doc": "doc",
    ".docx": "docx",
    ".ppt": "ppt",
    ".pptx": "pptx",
    ".rtf": "rtf",
    ".odt": "odt",
    ".ods": "ods",
    ".rar": "rar",
    ".7z": "7z",
    ".gz": "gz",
    ".tar": "tar",
}


def _path_suffix(url: str) -> str:
    try:
        path = urlparse(url).path.lower()
    except Exception:
        return ""
    if "." not in path:
        return ""
    return path[path.rfind(".") :]


def classify_asset_url(absolute_url: str) -> tuple[str | None, str | None]:
    """
    Return ``(file_type, category)`` where category is ``image`` or ``file`` or ``None``.
    Does not HEAD; uses path heuristics only.
    """
    suf = _path_suffix(absolute_url)
    if suf in _IMAGE_EXT:
        return suf.lstrip("."), "image"
    if suf in _DOC_EXT:
        return _DOC_EXT[suf], "file"
    if suf:
        return suf.lstrip(".") or "unknown", "file"
    return None, None


def _first_srcset_url(raw_srcset: str) -> str:
    for part in (raw_srcset or "").split(","):
        bit = part.strip().split()[0] if part.strip() else ""
        if bit and not bit.startswith("data:"):
            return bit
    return ""


def _append_image(out: list[dict[str, Any]], seen: set[str], base_url: str, raw_href: str) -> None:
    raw = (raw_href or "").strip()
    if not raw or raw.startswith("data:"):
        return
    abs_u = urljoin(base_url, raw)
    canonical, _frag = urldefrag(abs_u)
    if canonical in seen:
        return
    ft, cat = classify_asset_url(canonical)
    if cat != "image" and ft is None:
        # Allow extensionless CDN paths only when meta/link strongly imply image
        return
    seen.add(canonical)
    out.append(
        {
            "file_url": canonical,
            "file_type": ft or "image",
            "source_url": base_url,
        },
    )


def _images_from_meta_link_jsonld(soup: BeautifulSoup, base_url: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for attrs in (
        {"property": "og:image"},
        {"property": "og:image:url"},
        {"property": "og:image:secure_url"},
        {"name": "twitter:image"},
        {"name": "twitter:image:src"},
    ):
        m = soup.find("meta", attrs=attrs)
        if m and m.get("content"):
            _append_image(out, seen, base_url, str(m["content"]))

    for m in soup.find_all("meta", attrs={"itemprop": "image"}):
        if m.get("content"):
            _append_image(out, seen, base_url, str(m["content"]))

    for link in soup.find_all("link", href=True):
        rel = link.get("rel")
        rels = [rel] if isinstance(rel, str) else (list(rel) if rel else [])
        rel_l = {str(r).lower() for r in rels}
        if not rel_l & {"icon", "shortcut icon", "apple-touch-icon", "apple-touch-icon-precomposed", "image_src"}:
            continue
        _append_image(out, seen, base_url, str(link.get("href") or ""))

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue

        def walk_img(o: object, depth: int = 0) -> None:
            if depth > 12:
                return
            if isinstance(o, dict):
                img = o.get("image")
                if isinstance(img, str):
                    _append_image(out, seen, base_url, img)
                elif isinstance(img, list):
                    for it in img:
                        if isinstance(it, str):
                            _append_image(out, seen, base_url, it)
                        elif isinstance(it, dict) and it.get("url"):
                            _append_image(out, seen, base_url, str(it["url"]))
                elif isinstance(img, dict) and img.get("url"):
                    _append_image(out, seen, base_url, str(img["url"]))
                for v in o.values():
                    walk_img(v, depth + 1)
            elif isinstance(o, list):
                for it in o:
                    walk_img(it, depth + 1)

        walk_img(data)

    return out


def extract_image_urls_from_html(html: str, base_url: str) -> list[dict[str, Any]]:
    """Collect ``<img>``, ``<picture>``, meta/twitter/og images, icons, and JSON-LD ``image``."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    soup = BeautifulSoup(html, "html.parser")
    for img in soup.find_all("img"):
        raw = (img.get("src") or "").strip()
        if not raw or raw.startswith("data:"):
            raw = _first_srcset_url(str(img.get("srcset") or ""))
        if not raw:
            continue
        _append_image(out, seen, base_url, raw)

    for pic in soup.find_all("picture"):
        for src in pic.find_all("source", srcset=True):
            u = _first_srcset_url(str(src.get("srcset") or ""))
            if u:
                _append_image(out, seen, base_url, u)
        im = pic.find("img")
        if im:
            u = (im.get("src") or "").strip() or _first_srcset_url(str(im.get("srcset") or ""))
            if u:
                _append_image(out, seen, base_url, u)

    for extra in _images_from_meta_link_jsonld(soup, base_url):
        if extra["file_url"] not in seen:
            seen.add(extra["file_url"])
            out.append(extra)
    return out


def file_links_from_html(html: str, page_url: str) -> list[dict[str, Any]]:
    """Collect ``<a href>`` pointing at document-like paths (no download)."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        raw = str(a.get("href") or "").strip()
        if not raw or raw.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        abs_u = urljoin(page_url, raw)
        canonical, _ = urldefrag(abs_u)
        if not canonical.startswith(("http://", "https://")):
            continue
        ft, cat = classify_asset_url(canonical)
        if cat != "file" or not ft:
            continue
        if canonical in seen:
            continue
        seen.add(canonical)
        out.append({"file_url": canonical, "file_type": ft, "source_url": page_url})
    return out


def file_links_from_page_links(
    links: list[dict[str, Any]],
    page_url: str,
) -> list[dict[str, Any]]:
    """From ``ExtractedLink``-like dicts, keep URLs that look like downloadable assets."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in links:
        href = str((item or {}).get("href") or "").strip()
        if not href:
            continue
        abs_h = urljoin(page_url, href) if not href.startswith(("http://", "https://")) else href
        canonical, _ = urldefrag(abs_h)
        ft, cat = classify_asset_url(canonical)
        if cat != "file" or not ft:
            continue
        if canonical in seen:
            continue
        seen.add(canonical)
        out.append({"file_url": canonical, "file_type": ft, "source_url": page_url})
    return out


def _merge_file_link_rows(*parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for lst in parts:
        for it in lst:
            u = str((it or {}).get("file_url") or "").strip()
            if not u or u in seen:
                continue
            seen.add(u)
            merged.append(it)
    return merged


def enrich_payload_with_assets(
    *,
    page_url: str,
    html: str | None,
    links: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return ``(images, file_links)`` reference lists for persistence (links only, no downloads)."""
    images = extract_image_urls_from_html(html, page_url) if html else []
    from_anchors = file_links_from_page_links(links, page_url)
    from_dom = file_links_from_html(html, page_url) if html else []
    file_links = _merge_file_link_rows(from_anchors, from_dom)
    return images, file_links
