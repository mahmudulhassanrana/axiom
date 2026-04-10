from __future__ import annotations

from datetime import datetime, timezone

from axiom_extractors import ExtractedDocument

from axiom_exporters import export_bytes


def _sample_doc() -> ExtractedDocument:
    return ExtractedDocument(
        url="https://example.com/",
        final_url="https://example.com/",
        title="Example",
        language="en",
        text="Hello world",
        links=[],
        extractor_kind="html_requests",
        http_status=200,
        fetched_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        metadata={"k": "v"},
    )


def test_json_roundtrip_shape() -> None:
    doc = _sample_doc()
    body, mt, ext = export_bytes(doc, "json")
    assert ext == "json"
    assert "application/json" in mt
    assert b"Hello world" in body


def test_csv_has_header() -> None:
    body, _, ext = export_bytes(_sample_doc(), "csv")
    assert ext == "csv"
    assert b"extractor_kind" in body
    assert b"Hello world" in body


def test_markdown_contains_title() -> None:
    body, _, ext = export_bytes(_sample_doc(), "markdown")
    assert ext == "md"
    assert b"# Example" in body


def test_html_is_doctype() -> None:
    body, _, ext = export_bytes(_sample_doc(), "html")
    assert ext == "html"
    assert body.startswith(b"<!DOCTYPE html>")
