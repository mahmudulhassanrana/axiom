from __future__ import annotations

import os
import random
from typing import Any, Literal

from playwright.sync_api import sync_playwright

from axiom_extractors.models import ExtractedDocument
from axiom_extractors.parsing import build_document_from_html

WaitUntil = Literal["commit", "domcontentloaded", "load", "networkidle"]

_PW_USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
)


class PlaywrightExtractor:
    """
    Render the page in a headless browser and normalize the resulting HTML.

    Requires Playwright browsers: ``playwright install chromium``.
    """

    def __init__(
        self,
        *,
        timeout_ms: int = 30_000,
        wait_until: WaitUntil = "domcontentloaded",
        browser: Literal["chromium", "firefox", "webkit"] = "chromium",
        user_agent: str | None = None,
    ) -> None:
        self.timeout_ms = timeout_ms
        self.wait_until = wait_until
        self.browser = browser
        self._user_agent = user_agent

    def extract(self, url: str, *, include_html: bool = False) -> ExtractedDocument:
        metadata: dict[str, Any] = {
            "wait_until": self.wait_until,
            "browser": self.browser,
        }
        effective_ua = self._user_agent or random.choice(_PW_USER_AGENTS)
        with sync_playwright() as p:
            launcher = getattr(p, self.browser)
            browser = launcher.launch(headless=True)
            try:
                context = browser.new_context(user_agent=effective_ua)
                try:
                    page = context.new_page()
                    response = page.goto(url, wait_until=self.wait_until, timeout=self.timeout_ms)
                    status = response.status if response is not None else None
                    final_url = page.url
                    # Vue/React/Inertia: wait for network to settle so #app is hydrated (skippable via env).
                    skip_idle = os.environ.get("AXIOM_PLAYWRIGHT_SKIP_NETWORKIDLE", "").strip().lower() in (
                        "1",
                        "true",
                        "yes",
                    )
                    if not skip_idle:
                        try:
                            page.wait_for_load_state(
                                "networkidle",
                                timeout=min(12_000, self.timeout_ms),
                            )
                        except Exception:
                            pass
                    extra_ms = int((os.environ.get("AXIOM_PLAYWRIGHT_POST_GOTO_MS") or "0").strip() or 0)
                    extra_ms = max(0, min(extra_ms, 30_000))
                    if extra_ms > 0:
                        page.wait_for_timeout(extra_ms)
                    html = page.content()
                finally:
                    context.close()
            finally:
                browser.close()

        return build_document_from_html(
            url=url,
            final_url=final_url,
            http_status=status,
            html=html,
            extractor_kind="playwright",
            include_html=include_html,
            metadata=metadata,
        )
