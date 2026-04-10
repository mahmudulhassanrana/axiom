from __future__ import annotations

from typing import Any, Literal

from playwright.sync_api import sync_playwright

from axiom_extractors.models import ExtractedDocument
from axiom_extractors.parsing import build_document_from_html

WaitUntil = Literal["commit", "domcontentloaded", "load", "networkidle"]


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
        with sync_playwright() as p:
            launcher = getattr(p, self.browser)
            browser = launcher.launch(headless=True)
            try:
                context = (
                    browser.new_context(user_agent=self._user_agent)
                    if self._user_agent
                    else browser.new_context()
                )
                try:
                    page = context.new_page()
                    response = page.goto(url, wait_until=self.wait_until, timeout=self.timeout_ms)
                    status = response.status if response is not None else None
                    final_url = page.url
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
