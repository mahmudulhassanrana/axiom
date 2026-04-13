from __future__ import annotations

import os
import random

import requests

from axiom_extractors.models import ExtractedDocument
from axiom_extractors.parsing import build_document_from_html

DEFAULT_USER_AGENT = "AxiomExtractor/0.1 (+https://axiom.local)"

# Default cap for raw response bytes (news sites with heavy HTML + include_html can exceed 5MB).
_DEFAULT_HTML_MAX_BYTES = 15_000_000


def _max_bytes_from_env(fallback: int = _DEFAULT_HTML_MAX_BYTES) -> int | None:
    raw = (os.environ.get("AXIOM_HTML_MAX_BYTES") or "").strip()
    if not raw:
        return fallback
    try:
        v = int(raw, 10)
    except ValueError:
        return fallback
    if v <= 0:
        return None
    return max(4096, v)


# Rotated per request (compliant static pool; does not bypass bot defenses).
_USER_AGENTS = (
    DEFAULT_USER_AGENT,
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
)


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
        max_bytes: int | None = None,
    ) -> None:
        raw = (os.environ.get("AXIOM_HTML_FETCH_TIMEOUT") or "").strip()
        if timeout is None:
            self.timeout = float(raw) if raw else 30.0
        else:
            self.timeout = timeout
        self.max_bytes = max_bytes if max_bytes is not None else _max_bytes_from_env()
        self._session = session or requests.Session()
        base_headers = {"User-Agent": DEFAULT_USER_AGENT}
        if headers:
            base_headers.update(headers)
        self._session.headers.update(base_headers)

    def extract(self, url: str, *, include_html: bool = False) -> ExtractedDocument:
        req_headers = dict(self._session.headers)
        req_headers["User-Agent"] = random.choice(_USER_AGENTS)
        response = self._session.get(url, timeout=self.timeout, headers=req_headers)
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
