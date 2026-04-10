"""Smoke tests that shared testkit fixtures are available (extractor package)."""

from axiom_extractors.parsing import build_document_from_html


def test_sample_html_document_fixture(sample_html_document: str, sample_url: str) -> None:
    assert "Hello from testkit" in sample_html_document
    doc = build_document_from_html(
        url=sample_url,
        final_url=sample_url,
        http_status=200,
        html=sample_html_document,
        extractor_kind="html_requests",
        include_html=False,
        metadata={},
    )
    assert doc.title == "Sample"
    assert "Hello from testkit" in doc.text
