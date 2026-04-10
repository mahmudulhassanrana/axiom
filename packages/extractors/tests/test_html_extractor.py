import responses

from axiom_extractors.html_extractor import HtmlExtractor


@responses.activate
def test_html_extractor_uses_requests_and_normalizes() -> None:
    body = """<!doctype html><html><head><title>T</title></head>
    <body><p>Hi</p><a href="/a">A</a></body></html>"""
    responses.add(
        responses.GET,
        "https://example.com/page",
        body=body,
        status=200,
        content_type="text/html; charset=utf-8",
    )
    ex = HtmlExtractor()
    doc = ex.extract("https://example.com/page")
    assert doc.extractor_kind == "html_requests"
    assert doc.http_status == 200
    assert doc.final_url == "https://example.com/page"
    assert doc.title == "T"
    assert "Hi" in doc.text
    assert any(link.href == "https://example.com/a" for link in doc.links)
    assert "text/html" in doc.metadata.get("content_type", "")
