from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import requests
from kombu.exceptions import OperationalError
from axiom_extractors import ExtractedDocument
from fastapi.testclient import TestClient

from axiom_api.main import app

client = TestClient(app)


def _sample_doc(url: str = "https://example.com/") -> ExtractedDocument:
    return ExtractedDocument(
        url=url,
        final_url=url,
        title="T",
        language="en",
        text="hello",
        links=[],
        extractor_kind="html_requests",
        http_status=200,
        fetched_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        metadata={},
    )


def test_scrape_async_enqueues_celery_task() -> None:
    sent = MagicMock()
    sent.id = "celery-task-id-1"
    with patch("axiom_api.routes.scrape.get_celery_app") as gc:
        gc.return_value.send_task.return_value = sent
        # Default: async Celery path (no body flag required).
        r = client.post("/scrape", json={"url": "https://example.com"})
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "queued"
    assert body["task_id"] == "celery-task-id-1"
    gc.return_value.send_task.assert_called_once()
    st_kw = gc.return_value.send_task.call_args.kwargs["kwargs"]
    assert st_kw["url"].rstrip("/") == "https://example.com"
    assert st_kw["engine"] == "html_requests"
    assert st_kw["include_html"] is False
    assert gc.return_value.send_task.call_args.args[0] == "axiom.scrape"


def test_scrape_sync_html_uses_extractor() -> None:
    doc = _sample_doc()
    with patch(
        "axiom_api.routes.scrape._html_extractor.extract",
        return_value=doc,
    ) as mocked:
        r = client.post(
            "/scrape",
            json={"url": "https://example.com", "engine": "html_requests", "async": False},
        )
    assert r.status_code == 200
    mocked.assert_called_once()
    assert mocked.call_args is not None
    assert mocked.call_args.kwargs["include_html"] is False
    assert mocked.call_args.args[0].rstrip("/") == "https://example.com"
    body = r.json()
    assert body["url"].rstrip("/") == "https://example.com"
    assert body["text"] == "hello"


def test_scrape_sync_playwright_uses_extractor() -> None:
    doc = _sample_doc()
    doc = doc.model_copy(update={"extractor_kind": "playwright"})
    with patch(
        "axiom_api.routes.scrape._playwright_extractor.extract",
        return_value=doc,
    ) as mocked:
        r = client.post(
            "/scrape",
            json={"url": "https://example.com", "engine": "playwright", "async": False},
        )
    assert r.status_code == 200
    mocked.assert_called_once()
    assert r.json()["extractor_kind"] == "playwright"


def test_scrape_value_error_maps_to_413() -> None:
    with patch(
        "axiom_api.routes.scrape._html_extractor.extract",
        side_effect=ValueError("Response body exceeds max_bytes=1"),
    ):
        r = client.post("/scrape", json={"url": "https://example.com", "async": False})
    assert r.status_code == 413


def test_scrape_broker_down_returns_503() -> None:
    with patch("axiom_api.routes.scrape.get_celery_app") as gc:
        gc.return_value.send_task.side_effect = OperationalError("nope")
        r = client.post("/scrape", json={"url": "https://example.com"})
    assert r.status_code == 503
    err = r.json()["error"]
    assert err["code"] == "service_unavailable"
    assert "queue" in err["message"].lower() or "unavailable" in err["message"].lower()


def test_scrape_http_error_maps_to_502() -> None:
    resp = requests.Response()
    resp.status_code = 502
    err = requests.HTTPError(response=resp)
    with patch(
        "axiom_api.routes.scrape._html_extractor.extract",
        side_effect=err,
    ):
        r = client.post("/scrape", json={"url": "https://example.com", "async": False})
    assert r.status_code == 502


def test_scrape_connection_error_maps_to_502() -> None:
    with patch(
        "axiom_api.routes.scrape._html_extractor.extract",
        side_effect=requests.ConnectionError("refused"),
    ):
        r = client.post("/scrape", json={"url": "https://example.com", "async": False})
    assert r.status_code == 502
