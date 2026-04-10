from fastapi.testclient import TestClient

from axiom_api.main import app

client = TestClient(app)


def test_security_headers_on_response() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
