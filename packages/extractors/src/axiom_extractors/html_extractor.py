from __future__ import annotations

import os

import requests

from axiom_extractors.models import ExtractedDocument
from axiom_extractors.parsing import build_document_from_html

DEFAULT_USER_AGENT = "AxiomExtractor/0.1 (+https://axiom.local)"


class HtmlExtractor:
    """
    Fetch static HTML with ``requests`` and normalize with BeautifulSoup.

    Callers must enforce robots.txt, rate limits, and site policies before fetching.
    """

    def __init__(
        self,
        *,
        timeout: float | None = None,
        session: requests.Session | None = None,
        headers: dict[str, str] | None = None,
        max_bytes: int | None = 5_000_000,
    ) -> None:
        raw = (os.environ.get("AXIOM_HTML_FETCH_TIMEOUT") or "").strip()
        if timeout is None:
            self.timeout = float(raw) if raw else 30.0
        else:
            self.timeout = timeout
        self.max_bytes = max_bytes
        self._session = session or requests.Session()
        base_headers = {"User-Agent": DEFAULT_USER_AGENT}
        if headers:
            base_headers.update(headers)
        self._session.headers.update(base_headers)

    def extract(self, url: str, *, include_html: bool = False) -> ExtractedDocument:
        response = self._session.get(url, timeout=self.timeout)
        response.raise_for_status()
        raw = response.content
        if self.max_bytes is not None and len(raw) > self.max_bytes:
            msg = f"Response body exceeds max_bytes={self.max_bytes}"
            raise ValueError(msg)
        html = response.text
        content_type = response.headers.get("Content-Type", "")
        return build_document_from_html(
            url=url,
            final_url=response.url,
            http_status=response.status_code,
            html=html,
            extractor_kind="html_requests",
            include_html=include_html,
            metadata={"content_type": content_type},
        )
