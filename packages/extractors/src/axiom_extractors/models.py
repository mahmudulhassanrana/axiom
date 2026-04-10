from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

ExtractorKind = Literal["html_requests", "playwright"]


class ExtractedLink(BaseModel):
    """Normalized hyperlink extracted from a document."""

    href: str = Field(description="Absolute or root-relative URL after resolution.")
    text: str | None = Field(default=None, description="Anchor text, whitespace-normalized.")


class ExtractedDocument(BaseModel):
    """
    Canonical extraction payload for indexing, ML, or storage.

    ``text`` is plain visible text (scripts/styles removed, whitespace collapsed).
    """

    url: str = Field(description="Requested URL.")
    final_url: str | None = Field(
        default=None,
        description="URL after HTTP redirects or final navigation URL.",
    )
    title: str | None = Field(default=None, description="Document title if present.")
    language: str | None = Field(
        default=None,
        description="Best-effort language (e.g. html lang attribute).",
    )
    text: str = Field(description="Normalized visible text content.")
    links: list[ExtractedLink] = Field(default_factory=list)
    extractor_kind: ExtractorKind
    http_status: int | None = Field(
        default=None,
        description="HTTP status when applicable (HTML fetch).",
    )
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when extraction finished.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extractor-specific metadata (headers, timings, etc.).",
    )
    html: str | None = Field(
        default=None,
        description="Optional raw HTML snapshot when include_html=True.",
    )

    def to_json_dict(self) -> dict[str, Any]:
        """JSON-serializable dict (ISO-8601 datetimes)."""
        return self.model_dump(mode="json")
