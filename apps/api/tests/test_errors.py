"""Error envelope and request id behavior."""

from fastapi.testclient import TestClient

from axiom_api.deps.auth import get_current_user, get_current_user_bearer
from axiom_api.main import app

client = TestClient(app)


def test_validation_error_envelope() -> None:
    r = client.post("/scrape", json={})
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["request_id"] is not None
    assert "fields" in body["error"]
    assert r.headers.get("x-request-id")


def test_unauthorized_envelope() -> None:
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_user_bearer, None)
    r = client.get("/auth/me")
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] == "unauthorized"
    assert body["error"]["message"]
    assert r.headers.get("x-request-id")


def test_custom_request_id_header_round_trips() -> None:
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_user_bearer, None)
    rid = "test-req-id-abc"
    r = client.get("/auth/me", headers={"X-Request-ID": rid})
    assert r.status_code == 401
    assert r.headers.get("x-request-id") == rid
    assert r.json()["error"]["request_id"] == rid
