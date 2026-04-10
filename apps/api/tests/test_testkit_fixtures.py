"""Smoke tests that shared testkit fixtures are available (API package)."""

from __future__ import annotations

import uuid


def test_sample_uuid_fixtures(
    sample_organization_id: uuid.UUID,
    sample_user_id: uuid.UUID,
    sample_job_id: uuid.UUID,
    sample_schedule_id: uuid.UUID,
) -> None:
    assert sample_organization_id != sample_user_id
    assert len({sample_organization_id, sample_user_id, sample_job_id, sample_schedule_id}) == 4


def test_sample_job_create_body_shape(sample_job_create_body: dict) -> None:
    assert sample_job_create_body["url"].startswith("https://")
    assert sample_job_create_body["engine"] == "html_requests"


def test_sample_schedule_create_body_shape(sample_schedule_create_body: dict) -> None:
    assert sample_schedule_create_body["name"]
    assert sample_schedule_create_body["cron_expression"]
    assert "url" in sample_schedule_create_body["payload"]
