from __future__ import annotations

import hashlib
import html as html_stdlib
import json as json_lib
import re
from typing import Any
from urllib.parse import urlparse, urldefrag, urljoin

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


def _fallback_text_from_head(soup: BeautifulSoup, title: str | None) -> str:
    """
    When the body has no visible text (common for JS app shells), use title and
    standard meta descriptions so ``html_requests`` still captures page intent.
    """
    parts: list[str] = []
    seen: set[str] = set()

    def add_part(raw: str) -> None:
        n = normalize_whitespace(raw.strip())
        if n and n not in seen:
            seen.add(n)
            parts.append(n)

    if title:
        add_part(title)

    for attrs in (
        {"name": "description"},
        {"property": "og:description"},
        {"name": "twitter:description"},
        {"property": "twitter:description"},
    ):
        m = soup.find("meta", attrs=attrs)
        if m and m.get("content"):
            add_part(str(m["content"]))

    for attrs in (
        {"property": "og:title"},
        {"name": "twitter:title"},
    ):
        m = soup.find("meta", attrs=attrs)
        if m and m.get("content"):
            add_part(str(m["content"]))

    for attrs in ({"name": "keywords"}, {"name": "author"}):
        m = soup.find("meta", attrs=attrs)
        if m and m.get("content"):
            add_part(str(m["content"]))

    return "\n\n".join(parts)


def _walk_jsonld_for_text_and_urls(
    obj: Any,
    *,
    texts: list[str],
    urls: set[str],
    depth: int = 0,
) -> None:
    """Pull human-readable strings and http(s) URLs from JSON-LD (Person, WebSite, etc.)."""
    if depth > 14:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("@context",):
                continue
            lk = str(k).lower()
            if lk in ("sameas", "isrelatedto"):
                if isinstance(v, str) and v.startswith(("http://", "https://")):
                    urls.add(urldefrag(v)[0])
                elif isinstance(v, list):
                    for it in v:
                        if isinstance(it, str) and it.startswith(("http://", "https://")):
                            urls.add(urldefrag(it)[0])
                continue
            if lk == "url" and isinstance(v, str) and v.startswith(("http://", "https://")):
                urls.add(urldefrag(v)[0])
                continue
            if lk in (
                "description",
                "name",
                "jobtitle",
                "headline",
                "text",
                "abstract",
                "disambiguatingdescription",
            ) and isinstance(v, str):
                n = normalize_whitespace(v.strip())
                if len(n) > 2:
                    texts.append(n)
                continue
            _walk_jsonld_for_text_and_urls(v, texts=texts, urls=urls, depth=depth + 1)
    elif isinstance(obj, list):
        for it in obj:
            _walk_jsonld_for_text_and_urls(it, texts=texts, urls=urls, depth=depth + 1)


def _jsonld_text_and_link_urls(jld_blocks: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    texts: list[str] = []
    urls: set[str] = set()
    for block in jld_blocks:
        _walk_jsonld_for_text_and_urls(block, texts=texts, urls=urls, depth=0)
    seen_t: set[str] = set()
    uniq_texts: list[str] = []
    for t in texts:
        key = t.lower()[:500]
        if key in seen_t:
            continue
        seen_t.add(key)
        uniq_texts.append(t)
    return uniq_texts, sorted(urls)


def _inertia_data_page_text_fragments(soup: BeautifulSoup) -> list[str]:
    """Best-effort strings from Inertia ``#app[data-page]`` (often still sparse)."""
    app = soup.find(id="app")
    raw = app.get("data-page") if app else None
    if not raw or not isinstance(raw, str):
        return []
    try:
        decoded = html_stdlib.unescape(raw.strip())
        data = json_lib.loads(decoded)
    except (json_lib.JSONDecodeError, TypeError, ValueError):
        return []
    found: list[str] = []
    skip_keys = frozenset(
        {"component", "version", "encryptHistory", "clearHistory", "url", "errors", "locale"},
    )

    def walk(o: Any, depth: int = 0) -> None:
        if depth > 18 or len(found) > 80:
            return
        if isinstance(o, str):
            s = normalize_whitespace(o.strip())
            if len(s) >= 24 and not s.startswith(("{", "[", "http://", "https://")):
                found.append(s)
        elif isinstance(o, dict):
            for kk, vv in o.items():
                if str(kk) in skip_keys:
                    continue
                walk(vv, depth + 1)
        elif isinstance(o, list):
            for it in o:
                walk(it, depth + 1)

    walk(data)
    seen: set[str] = set()
    out: list[str] = []
    for s in found:
        k = s.lower()[:400]
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out


def _looks_like_js_spa_shell(soup: BeautifulSoup, visible_body_text_len: int) -> bool:
    if visible_body_text_len > 500:
        return False
    body = soup.body
    if not body:
        return visible_body_text_len < 120
    work = BeautifulSoup(str(body), "html.parser")
    _strip_noise_tags(work)
    root = work.body if work.body else work
    t = normalize_whitespace(root.get_text(" ", strip=True))
    if len(t) < 100:
        return True
    if soup.find(id="app") is not None and len(t) < 400:
        return True
    return False


def _merge_extracted_links(
    base: list[ExtractedLink],
    extra_hrefs: list[str],
    *,
    label: str,
) -> list[ExtractedLink]:
    seen = {(l.href, l.text) for l in base}
    out = list(base)
    for href in extra_hrefs:
        canonical, _f = urldefrag(href)
        key = (canonical, label)
        if key in seen:
            continue
        seen.add(key)
        out.append(ExtractedLink(href=canonical, text=label))
    return out


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


def _hostname_lower(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _dedupe_line_blocks(text: str) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        n = normalize_whitespace(raw)
        if not n:
            continue
        key = n.lower()[:3000]
        if key in seen:
            continue
        seen.add(key)
        out.append(n)
    return "\n".join(out)


def extract_headings_from_soup(soup: BeautifulSoup, *, max_items: int = 200) -> list[dict[str, Any]]:
    work = BeautifulSoup(str(soup), "html.parser")
    _strip_noise_tags(work)
    root = work.body if work.body else work
    headings: list[dict[str, Any]] = []
    for el in root.find_all(re.compile(r"^h[1-6]$", re.I)):
        if len(headings) >= max_items:
            break
        t = normalize_whitespace(el.get_text(" ", strip=True))
        if not t:
            continue
        try:
            level = int(el.name[1])
        except (TypeError, ValueError):
            continue
        headings.append({"level": level, "text": t})
    return headings


def extract_paragraph_blocks_from_soup(soup: BeautifulSoup, *, max_items: int = 400) -> list[str]:
    """Visible-ish blocks (p, li, td, …) with duplicate suppression."""
    work = BeautifulSoup(str(soup), "html.parser")
    _strip_noise_tags(work)
    root = work.find("article") or work.find("main") or work.body or work
    seen: set[str] = set()
    paras: list[str] = []
    for el in root.find_all(("p", "li", "blockquote", "td", "th", "dd", "dt", "figcaption")):
        if len(paras) >= max_items:
            break
        t = normalize_whitespace(el.get_text(" ", strip=True))
        if len(t) < 2:
            continue
        key = t.lower()[:2000]
        if key in seen:
            continue
        seen.add(key)
        paras.append(t)
    return paras


def categorize_links_by_host(links: list[ExtractedLink], base_url: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    seed_h = _hostname_lower(base_url)
    internal: list[dict[str, Any]] = []
    external: list[dict[str, Any]] = []
    for link in links:
        d = link.model_dump(mode="json")
        lh = _hostname_lower(link.href)
        if seed_h and lh and lh != seed_h:
            external.append(d)
        else:
            internal.append(d)
    return internal, external


def content_quality_score(
    text: str,
    headings: list[dict[str, Any]],
    meta_tags: dict[str, str],
) -> float:
    score = 0.0
    L = len(text.strip())
    if L > 4000:
        score += 0.36
    elif L > 1200:
        score += 0.30
    elif L > 400:
        score += 0.22
    elif L > 120:
        score += 0.14
    elif L > 40:
        score += 0.08
    elif L > 0:
        score += 0.03
    if headings:
        score += min(0.28, 0.035 * len(headings))
    if meta_tags:
        for k in ("description", "og:title", "og:description", "twitter:description", "keywords"):
            if meta_tags.get(k):
                score += 0.08
                break
    return min(1.0, round(score, 4))


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
    meta_tags = _meta_tags(soup)
    jld = _json_ld_from_soup(soup)
    jld_texts, jld_hrefs = _jsonld_text_and_link_urls(jld)
    headings = extract_headings_from_soup(soup)
    paras = extract_paragraph_blocks_from_soup(soup)
    broad = visible_text_from_soup(soup)
    structured = "\n\n".join(paras) if paras else ""
    if len(structured.strip()) >= max(120, int(len(broad.strip()) * 0.55)):
        text = structured
    else:
        text = broad
    text = _dedupe_line_blocks(text)
    if not text.strip():
        text = _fallback_text_from_head(soup, title)
    # Vue/React/Inertia shells: merge JSON-LD + data-page strings so http scrapes match visible intent.
    shell = _looks_like_js_spa_shell(soup, len(broad.strip()))
    inertia_bits = _inertia_data_page_text_fragments(soup)
    static_enrich = "\n\n".join([*jld_texts, *inertia_bits])
    if static_enrich.strip() and (shell or len(text.strip()) < 500):
        if text.strip():
            text = f"{text.rstrip()}\n\n---\n{static_enrich.strip()}"
        else:
            text = static_enrich.strip()
    text = _dedupe_line_blocks(text)
    links = _merge_extracted_links(
        extract_links_from_soup(soup, base_url=base),
        jld_hrefs,
        label="json-ld",
    )
    internal, external = categorize_links_by_host(links, base)
    meta = dict(metadata or {})
    meta.setdefault("meta_tags", meta_tags)
    meta["headings"] = headings
    meta["paragraphs"] = paras[:300]
    meta["full_text"] = text
    meta["internal_links"] = internal[:400]
    meta["external_links"] = external[:400]
    meta["content_quality_score"] = content_quality_score(text, headings, meta_tags)
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
