from datetime import datetime, timezone

from axiom_extractors.models import ExtractedDocument, ExtractedLink


def test_extracted_document_json_roundtrip() -> None:
    doc = ExtractedDocument(
        url="https://a.test/",
        final_url="https://a.test/x",
        title="T",
        language="en",
        text="body",
        links=[ExtractedLink(href="https://a.test/l", text="L")],
        extractor_kind="html_requests",
        http_status=200,
        fetched_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        metadata={"a": 1},
    )
    payload = doc.to_json_dict()
    assert payload["url"] == "https://a.test/"
    assert payload["links"][0]["href"] == "https://a.test/l"
    assert payload["fetched_at"].startswith("2020-01-01")
