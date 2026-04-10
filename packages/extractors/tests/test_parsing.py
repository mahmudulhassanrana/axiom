from axiom_extractors.parsing import (
    build_document_from_html,
    normalize_whitespace,
)


def test_normalize_whitespace() -> None:
    assert normalize_whitespace("  a \n\n  b  ") == "a\nb"


def test_build_document_from_html_basic() -> None:
    html = """<!doctype html>
    <html lang="en-GB">
    <head><title> Hello  world </title></head>
    <body>
      <script>alert(1)</script>
      <p>First</p>
      <a href="/rel">Link text</a>
      <a href="https://other.example/x">Abs</a>
    </body>
    </html>"""
    doc = build_document_from_html(
        url="https://example.com/start",
        final_url="https://example.com/final",
        http_status=200,
        html=html,
        extractor_kind="html_requests",
        include_html=False,
        metadata={"k": "v"},
    )
    assert doc.url == "https://example.com/start"
    assert doc.final_url == "https://example.com/final"
    assert doc.title == "Hello world"
    assert doc.language == "en-GB"
    assert doc.http_status == 200
    assert doc.extractor_kind == "html_requests"
    assert "First" in doc.text
    assert "alert" not in doc.text
    assert doc.html is None
    hrefs = {link.href for link in doc.links}
    assert "https://example.com/rel" in hrefs
    assert "https://other.example/x" in hrefs
    assert doc.metadata["k"] == "v"


def test_build_document_include_html() -> None:
    doc = build_document_from_html(
        url="https://example.com/",
        final_url=None,
        http_status=None,
        html="<html><body><p>x</p></body></html>",
        extractor_kind="playwright",
        include_html=True,
    )
    assert doc.html is not None
    assert "<p>x</p>" in doc.html
