from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from axiom_api.main import app

pytestmark = pytest.mark.needs_real_auth

client = TestClient(app)


@pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL required for auth integration tests",
)
def test_register_login_me_and_api_key_roundtrip() -> None:
    suffix = uuid.uuid4().hex[:8]
    email = f"user{suffix}@example.com"
    slug = f"org-{suffix}"

    r = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "Longpassword12",
            "organization_name": "Test Org",
            "organization_slug": slug,
            "full_name": "Tester",
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["user"]["email"] == email
    assert data["user"]["role"] == "admin"
    token = data["access_token"]

    r2 = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["email"] == email

    r3 = client.post(
        "/auth/api-keys",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "ci key"},
    )
    assert r3.status_code == 201, r.text
    raw_key = r3.json()["key"]
    assert raw_key.startswith("axk_")

    r4 = client.get("/auth/me", headers={"X-API-Key": raw_key})
    assert r4.status_code == 200
    assert r4.json()["email"] == email

    r5 = client.get("/admin/ping", headers={"Authorization": f"Bearer {token}"})
    assert r5.status_code == 200

    r6 = client.post(
        "/admin/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "email": f"member{suffix}@example.com",
            "password": "Longpassword22",
            "role": "user",
        },
    )
    assert r6.status_code == 201, r.text
    assert r6.json()["role"] == "user"

    login = client.post(
        "/auth/login",
        json={"email": f"member{suffix}@example.com", "password": "Longpassword22"},
    )
    assert login.status_code == 200
    member_token = login.json()["access_token"]

    r7 = client.get("/admin/ping", headers={"Authorization": f"Bearer {member_token}"})
    assert r7.status_code == 403
