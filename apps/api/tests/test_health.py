from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from axiom_api.db.deps import get_db
from axiom_api.main import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_ready_ok() -> None:
    async def _db_ok():
        session = MagicMock(spec=AsyncSession)
        session.execute = AsyncMock(return_value=None)
        yield session

    app.dependency_overrides[get_db] = _db_ok
    try:
        r = client.get("/health/ready")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["database"] == "connected"


def test_health_ready_unready() -> None:
    async def _db_fail():
        session = MagicMock(spec=AsyncSession)
        session.execute = AsyncMock(side_effect=RuntimeError("db down"))
        yield session

    app.dependency_overrides[get_db] = _db_fail
    try:
        r = client.get("/health/ready")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 503
    assert r.json()["status"] == "unready"
