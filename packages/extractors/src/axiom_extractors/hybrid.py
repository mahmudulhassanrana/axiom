"""Static HTML first, Playwright when content is empty or below quality thresholds."""

from __future__ import annotations

import logging
from typing import Literal

from axiom_extractors.crawl_constants import MIN_CRAWL_CHARS, MIN_CRAWL_QUALITY
from axiom_extractors.html_extractor import HtmlExtractor
from axiom_extractors.models import ExtractedDocument
from axiom_extractors.playwright_extractor import PlaywrightBrowserSession, PlaywrightExtractor

logger = logging.getLogger(__name__)

ExtractionType = Literal["static", "js"]


def _doc_insufficient(doc: ExtractedDocument) -> bool:
    body = (doc.text or "").strip()
    if not body:
        return True
    meta = doc.metadata if isinstance(doc.metadata, dict) else {}
    try:
        q = float(meta.get("content_quality_score") or 0.0)
    except (TypeError, ValueError):
        q = 0.0
    if q < MIN_CRAWL_QUALITY and len(body) < MIN_CRAWL_CHARS:
        return True
    return False


def _spa_shell_needs_browser(doc: ExtractedDocument) -> bool:
    """Vue/React/Laravel shells: tiny body text but HTML shows #app mount."""
    html = (doc.html or "") if isinstance(doc.html, str) else ""
    if not html:
        return False
    hlow = html.lower()
    if 'id="app"' not in hlow and "id='app'" not in hlow:
        return False
    body = (doc.text or "").strip()
    if len(body) >= 2500:
        return False
    return True


def extract_for_crawl_engine(
    *,
    url: str,
    include_html: bool,
    engine: Literal["html_requests", "playwright"],
    html_ex: HtmlExtractor,
    pw_ex: PlaywrightExtractor,
    pw_session: PlaywrightBrowserSession | None = None,
) -> tuple[ExtractedDocument, ExtractionType]:
    """
    ``html_requests``: static fetch first; Playwright if content is empty/low quality.
    ``playwright``: headless only.
    """
    if engine == "playwright":
        logger.info("hybrid.js_rendering_triggered", extra={"url": url, "mode": "playwright_engine"})
        doc = pw_ex.extract(url, include_html=include_html, session=pw_session)
        return doc, "js"

    static_doc = html_ex.extract(url, include_html=True)
    thin = _doc_insufficient(static_doc) or _spa_shell_needs_browser(static_doc)
    if not thin:
        if not include_html and static_doc.html:
            static_doc = static_doc.model_copy(update={"html": None})
        return static_doc, "static"

    logger.info(
        "hybrid.fallback_playwright",
        extra={
            "url": url,
            "static_chars": len((static_doc.text or "").strip()),
            "spa_shell": _spa_shell_needs_browser(static_doc),
        },
    )
    logger.info("hybrid.js_rendering_triggered", extra={"url": url})
    js_doc = pw_ex.extract(url, include_html=include_html, session=pw_session)
    meta = dict(js_doc.metadata or {})
    meta["hybrid_static_attempted"] = True
    meta["hybrid_static_chars"] = len((static_doc.text or "").strip())
    meta["hybrid_static_quality"] = (
        float(static_doc.metadata.get("content_quality_score") or 0.0)
        if isinstance(static_doc.metadata, dict)
        else 0.0
    )
    merged = js_doc.model_copy(update={"metadata": meta})
    return merged, "js"
