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
    assert doc.metadata.get("full_text")
    assert isinstance(doc.metadata.get("headings"), list)
    assert isinstance(doc.metadata.get("content_quality_score"), float)
    intl = doc.metadata.get("internal_links") or []
    extl = doc.metadata.get("external_links") or []
    assert any("example.com/rel" in str(x.get("href", "")) for x in intl)
    assert any("other.example" in str(x.get("href", "")) for x in extl)


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


def test_build_document_js_shell_uses_head_fallback() -> None:
    """SPA shells often have empty body text but rich <title> and meta descriptions."""
    html = """<!doctype html>
<html lang="en"><head>
  <title>My Portfolio</title>
  <meta name="description" content="Engineer building web apps.">
  <meta property="og:description" content="Open graph summary.">
</head><body><div id="app"></div></body></html>"""
    doc = build_document_from_html(
        url="https://example.com/",
        final_url="https://example.com/",
        http_status=200,
        html=html,
        extractor_kind="html_requests",
        include_html=False,
    )
    assert "My Portfolio" in doc.text
    assert "Engineer building web apps" in doc.text
    assert "Open graph summary" in doc.text


def test_vue_inertia_shell_jsonld_og_images_and_sameas() -> None:
    """Static HTML like mahmudrana.dev: empty #app, real content in JSON-LD + meta."""
    from axiom_extractors.assets import extract_image_urls_from_html

    html = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8"/>
<title>MD. Example - Developer</title>
<meta name="description" content="Short meta blurb.">
<meta property="og:image" content="https://www.example.dev/pic/profile.jpg">
<link rel="icon" href="/pic/profile.jpg"/>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Person",
  "name": "Md. Example Dev",
  "jobTitle": "Software Engineer",
  "url": "https://www.example.dev",
  "image": "https://www.example.dev/pic/profile.jpg",
  "sameAs": [
    "https://github.com/example",
    "https://www.linkedin.com/in/example/"
  ],
  "description": "Results-driven engineer with expertise in Laravel, Vue.js, and APIs."
}
</script>
</head><body><div id="app" data-page="{&quot;component&quot;:&quot;Home&quot;}"></div></body></html>"""
    doc = build_document_from_html(
        url="https://example.dev/",
        final_url="https://www.example.dev/",
        http_status=200,
        html=html,
        extractor_kind="html_requests",
        include_html=False,
    )
    assert "Laravel" in doc.text or "Vue.js" in doc.text
    assert "Md. Example Dev" in doc.text
    assert any("github.com/example" in link.href for link in doc.links)
    assert any("linkedin.com" in link.href for link in doc.links)

    imgs = extract_image_urls_from_html(html, "https://www.example.dev/")
    urls = {i["file_url"] for i in imgs}
    assert "https://www.example.dev/pic/profile.jpg" in urls
