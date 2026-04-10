"""Smoke tests that shared testkit fixtures are available (exporters package)."""

from datetime import datetime, timezone

from axiom_extractors import ExtractedDocument
from axiom_exporters import export_bytes


def test_sample_url_roundtrip_json(sample_url: str) -> None:
    doc = ExtractedDocument(
        url=sample_url,
        final_url=sample_url,
        title="T",
        language="en",
        text="x",
        links=[],
        extractor_kind="html_requests",
        http_status=200,
        fetched_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        metadata={},
    )
    body, _, _ = export_bytes(doc, "json")
    assert sample_url.encode() in body
