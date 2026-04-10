"""Structured access logs and request / trace correlation."""

import logging

import pytest
from fastapi.testclient import TestClient

from axiom_api.deps.auth import get_current_user, get_current_user_bearer
from axiom_api.main import app


def _allow_access_logs_to_caplog() -> None:
    """``axiom_api`` is configured with ``propagate=False``; caplog only sees the root stream."""
    logging.getLogger("axiom_api").propagate = True


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_x_request_id_header_always_present(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("x-request-id")


def test_custom_x_request_id_preserved(client: TestClient) -> None:
    rid = "client-trace-xyz"
    r = client.get("/health", headers={"X-Request-ID": rid})
    assert r.headers.get("x-request-id") == rid


def test_access_log_for_non_skipped_route(caplog: pytest.LogCaptureFixture) -> None:
    _allow_access_logs_to_caplog()
    caplog.set_level(logging.INFO, "axiom_api.access")
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_user_bearer, None)
    with TestClient(app) as client:
        client.get("/auth/me")
    assert any(getattr(r, "msg", "") == "http_request" for r in caplog.records)


def test_traceparent_correlates_access_log(caplog: pytest.LogCaptureFixture) -> None:
    _allow_access_logs_to_caplog()
    caplog.set_level(logging.INFO, "axiom_api.access")
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_user_bearer, None)
    trace = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    with TestClient(app) as client:
        r = client.get("/auth/me", headers={"traceparent": trace})
    assert r.status_code == 401
    recs = [r for r in caplog.records if getattr(r, "msg", "") == "http_request"]
    assert recs
    assert getattr(recs[0], "trace_id", None) == "4bf92f3577b34da6a3ce929d0e0e4736"
