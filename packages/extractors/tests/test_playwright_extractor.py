import urllib.parse

import pytest

pytest.importorskip("playwright.sync_api")

from playwright.sync_api import Error as PlaywrightError

from axiom_extractors.playwright_extractor import PlaywrightExtractor


def test_playwright_extractor_data_url() -> None:
    html = """<!doctype html><html lang="en"><head><title>Play</title></head>
    <body><p id="x">ok</p><script>document.getElementById('x').textContent='js';</script></body></html>"""
    url = "data:text/html;charset=utf-8," + urllib.parse.quote(html)
    try:
        doc = PlaywrightExtractor().extract(url)
    except PlaywrightError as exc:
        pytest.skip(f"Playwright browsers unavailable ({exc}). Run: playwright install chromium")

    assert doc.extractor_kind == "playwright"
    assert doc.title == "Play"
    assert "js" in doc.text
    assert doc.final_url is not None
    assert doc.final_url.startswith("data:text/html")
