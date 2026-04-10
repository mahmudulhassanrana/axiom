from fastapi.testclient import TestClient

from axiom_api.main import app

client = TestClient(app)


def test_openapi_json() -> None:
    r = client.get("/openapi.json")
    assert r.status_code == 200
    body = r.json()
    assert body["openapi"].startswith("3.")
    assert "paths" in body
    assert "/health" in body["paths"]


def test_docs_available() -> None:
    r = client.get("/docs")
    assert r.status_code == 200


def test_redoc_available() -> None:
    r = client.get("/redoc")
    assert r.status_code == 200
