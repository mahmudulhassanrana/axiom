from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from axiom_api.deps.auth import get_current_user, get_current_user_bearer
from axiom_api.main import app


@pytest.fixture(autouse=True)
def _disable_compliance_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPLIANCE_ENABLED", "false")


@pytest.fixture(autouse=True)
def _default_auth_dependency_override(request: pytest.FixtureRequest) -> None:
    """Scrape and other protected routes get a stub user unless marked @pytest.mark.needs_real_auth."""

    if request.node.get_closest_marker("needs_real_auth"):
        yield
        return

    async def _fake_user() -> SimpleNamespace:
        return SimpleNamespace(
            id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            email="test@example.com",
            full_name=None,
            created_at=datetime.now(UTC),
            role="user",
            is_active=True,
        )

    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_current_user_bearer] = _fake_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_user_bearer, None)
