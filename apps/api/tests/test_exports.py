from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from axiom_api.main import app

client = TestClient(app)


def test_export_download_json() -> None:
    doc = {
        "url": "https://example.com/",
        "final_url": "https://example.com/",
        "title": "T",
        "language": "en",
        "text": "hello",
        "links": [],
        "extractor_kind": "html_requests",
        "http_status": 200,
        "fetched_at": datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat(),
        "metadata": {},
    }
    r = client.post("/exports/download", json={"format": "json", "document": doc})
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith('attachment; filename="export.json"')
    assert "hello" in r.text


def test_export_download_csv() -> None:
    doc = {
        "url": "https://example.com/",
        "text": "x",
        "links": [],
        "extractor_kind": "html_requests",
        "fetched_at": datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat(),
        "metadata": {},
    }
    r = client.post("/exports/download", json={"format": "csv", "document": doc})
    assert r.status_code == 200
    assert "text" in r.text
