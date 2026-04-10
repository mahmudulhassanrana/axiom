from __future__ import annotations

from typing import Protocol

from axiom_extractors.models import ExtractedDocument


class Extractor(Protocol):
    """Pluggable extractor returning a normalized :class:`ExtractedDocument`."""

    def extract(self, url: str, *, include_html: bool = False) -> ExtractedDocument:
        """Fetch and parse ``url`` into a normalized document."""
        ...
