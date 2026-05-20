from __future__ import annotations

import json
import logging
import os
import random
from typing import Any, Literal

from playwright.sync_api import sync_playwright

from axiom_extractors.laravel_api_capture import (
    collect_extra_laravel_pages,
    is_laravel_paginated_json,
    pick_best_laravel_payload,
    records_text_block,
    normalize_member_row,
)
from axiom_extractors.human_browse import gradual_scroll
from axiom_extractors.models import ExtractedDocument
from axiom_extractors.parsing import build_document_from_html

logger = logging.getLogger(__name__)

WaitUntil = Literal["commit", "domcontentloaded", "load", "networkidle"]

_PW_USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
)


def _wait_selectors() -> list[str]:
    raw = (os.environ.get("AXIOM_PLAYWRIGHT_WAIT_SELECTORS") or "").strip()
    if raw:
        return [s.strip() for s in raw.split(",") if s.strip()]
    return [
        "main",
        "table tbody tr",
        "[class*='member']",
        ".dataTables_wrapper",
        ".card",
        "article",
    ]


class PlaywrightBrowserSession:
    """Reusable browser context for multi-page crawls (cookie/session continuity)."""

    def __init__(self, extractor: PlaywrightExtractor) -> None:
        self._ext = extractor
        self._playwright: Any = None
        self._browser: Any = None
        self.context: Any = None

    def start(self) -> PlaywrightBrowserSession:
        self._playwright = sync_playwright().start()
        launcher = getattr(self._playwright, self._ext.browser)
        self._browser = launcher.launch(headless=True)
        ua = self._ext._user_agent or random.choice(_PW_USER_AGENTS)
        self.context = self._browser.new_context(user_agent=ua)
        return self

    def stop(self) -> None:
        if self.context is not None:
            try:
                self.context.close()
            except Exception:
                pass
            self.context = None
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None


class PlaywrightExtractor:
    """
    Render the page in a headless browser and normalize the resulting HTML.

    Requires Playwright browsers: ``playwright install chromium``.
    """

    def __init__(
        self,
        *,
        timeout_ms: int = 30_000,
        wait_until: WaitUntil = "load",
        browser: Literal["chromium", "firefox", "webkit"] = "chromium",
        user_agent: str | None = None,
    ) -> None:
        self.timeout_ms = timeout_ms
        self.wait_until = wait_until
        self.browser = browser
        self._user_agent = user_agent

    def extract(
        self,
        url: str,
        *,
        include_html: bool = False,
        session: PlaywrightBrowserSession | None = None,
    ) -> ExtractedDocument:
        if session is not None and session.context is not None:
            html, final_url, status, metadata = self._render_url(
                url,
                context=session.context,
            )
        else:
            effective_ua = self._user_agent or random.choice(_PW_USER_AGENTS)
            with sync_playwright() as p:
                launcher = getattr(p, self.browser)
                browser = launcher.launch(headless=True)
                try:
                    context = browser.new_context(user_agent=effective_ua)
                    try:
                        html, final_url, status, metadata = self._render_url(url, context=context)
                    finally:
                        context.close()
                finally:
                    browser.close()

        doc = build_document_from_html(
            url=url,
            final_url=final_url,
            http_status=status,
            html=html,
            extractor_kind="playwright",
            include_html=include_html,
            metadata=metadata,
        )
        mrec = metadata.get("member_records")
        if isinstance(mrec, list) and mrec:
            block = records_text_block([r for r in mrec if isinstance(r, dict)])
            meta2 = dict(doc.metadata or {})
            meta2["member_records"] = mrec
            meta2.setdefault("pagination_source", metadata.get("pagination_source"))
            if metadata.get("captured_api_urls"):
                meta2["captured_api_urls"] = metadata["captured_api_urls"]
            extra_text = f"\n\n## Extracted member records ({len(mrec)})\n\n{block}"
            doc = doc.model_copy(
                update={
                    "text": f"{(doc.text or '').rstrip()}{extra_text}".strip(),
                    "metadata": meta2,
                },
            )
        return doc

    def _render_url(
        self,
        url: str,
        *,
        context: Any,
    ) -> tuple[str, str, int | None, dict[str, Any]]:
        metadata: dict[str, Any] = {
            "wait_until": self.wait_until,
            "browser": self.browser,
        }
        json_captures: list[dict[str, Any]] = []
        html = ""
        final_url = url
        status: int | None = None

        def on_response(response: Any) -> None:
            try:
                if response.status != 200:
                    return
                ct = (response.headers.get("content-type") or "").lower()
                if "json" not in ct:
                    return
                try:
                    raw_b = response.body()
                except Exception:
                    return
                try:
                    obj = json.loads(raw_b.decode("utf-8"))
                except Exception:
                    return
                json_captures.append({"url": response.url, "json": obj})
            except Exception:
                return

        page = context.new_page()
        page.on("response", on_response)
        try:
            response = page.goto(url, wait_until=self.wait_until, timeout=self.timeout_ms)
            status = response.status if response is not None else None
            final_url = page.url
            skip_idle = os.environ.get("AXIOM_PLAYWRIGHT_SKIP_NETWORKIDLE", "").strip().lower() in (
                "1",
                "true",
                "yes",
            )
            if not skip_idle:
                try:
                    page.wait_for_load_state(
                        "networkidle",
                        timeout=min(15_000, self.timeout_ms),
                    )
                except Exception:
                    pass
            for sel in _wait_selectors():
                try:
                    page.wait_for_selector(sel, timeout=4_000, state="attached")
                    break
                except Exception:
                    continue
            extra_ms = int((os.environ.get("AXIOM_PLAYWRIGHT_POST_GOTO_MS") or "0").strip() or 0)
            extra_ms = max(0, min(extra_ms, 30_000))
            if extra_ms > 0:
                page.wait_for_timeout(extra_ms)
            gradual_scroll(page)
            html = page.content()
        finally:
            page.remove_listener("response", on_response)
            page.close()

        best = pick_best_laravel_payload(json_captures)
        member_records: list[dict[str, Any]] = []
        if best and isinstance(best.get("json"), dict):
            body = best["json"]
            if is_laravel_paginated_json(body):
                api_url = str(best.get("url") or "")
                meta = body.get("meta") if isinstance(body.get("meta"), dict) else {}
                logger.info(
                    "playwright.api_detected",
                    extra={"url": api_url, "first_page_rows": len(body.get("data") or [])},
                )
                for item in body.get("data") or []:
                    if isinstance(item, dict):
                        member_records.append(normalize_member_row(item, source_url=api_url))
                try:
                    more = collect_extra_laravel_pages(
                        request_get=context.request,
                        first_url=api_url,
                        meta=meta,
                        seed_url=url,
                        referer=final_url or url,
                        first_body=body,
                    )
                    member_records.extend(more)
                except Exception as exc:
                    logger.warning("playwright.api_pagination_failed", extra={"error": str(exc)})
                metadata["member_records"] = member_records
                metadata["captured_api_urls"] = [c.get("url") for c in json_captures if c.get("url")]
                metadata["pagination_source"] = "laravel_json_api"
                logger.info("playwright.records_extracted", extra={"count": len(member_records)})
        return html, final_url, status, metadata
