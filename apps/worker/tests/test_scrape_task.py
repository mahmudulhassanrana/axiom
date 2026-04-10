from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import requests
from axiom_extractors import ExtractedDocument

from axiom_worker.tasks.scrape import scrape_task


def _doc(url: str = "https://example.com/") -> ExtractedDocument:
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


def test_scrape_task_html_success(celery_eager) -> None:
    doc = _doc()
    with patch(
        "axiom_worker.tasks.scrape._html_extractor.extract",
        return_value=doc,
    ) as mocked:
        result = scrape_task.apply(
            kwargs={"url": "https://example.com", "engine": "html_requests"},
        )
    assert result.successful()
    mocked.assert_called_once()
    assert mocked.call_args.kwargs["include_html"] is False
    assert mocked.call_args.args[0].rstrip("/") == "https://example.com"
    assert result.result["text"] == "hello"


def test_scrape_task_invalid_engine_fails(celery_eager) -> None:
    with pytest.raises(ValueError, match="Unsupported engine"):
        scrape_task.apply(
            kwargs={"url": "https://example.com", "engine": "unknown"},
        )


def test_scrape_task_client_http_error_no_retry(celery_eager) -> None:
    resp = requests.Response()
    resp.status_code = 404
    err = requests.HTTPError(response=resp)
    with patch(
        "axiom_worker.tasks.scrape._html_extractor.extract",
        side_effect=err,
    ) as mocked:
        with pytest.raises(requests.HTTPError):
            scrape_task.apply(kwargs={"url": "https://example.com"})
    mocked.assert_called_once()
