"""Pytest plugin: registers shared fixtures when axiom-testkit is installed."""

from __future__ import annotations

import uuid

import pytest

from axiom_testkit import sample_data as sd


@pytest.fixture
def sample_organization_id() -> uuid.UUID:
    return sd.SAMPLE_ORGANIZATION_ID


@pytest.fixture
def sample_user_id() -> uuid.UUID:
    return sd.SAMPLE_USER_ID


@pytest.fixture
def sample_job_id() -> uuid.UUID:
    return sd.SAMPLE_JOB_ID


@pytest.fixture
def sample_schedule_id() -> uuid.UUID:
    return sd.SAMPLE_SCHEDULE_ID


@pytest.fixture
def sample_url() -> str:
    return sd.SAMPLE_URL


@pytest.fixture
def sample_cron_expression() -> str:
    return sd.SAMPLE_CRON_HOURLY


@pytest.fixture
def sample_timezone() -> str:
    return sd.SAMPLE_TIMEZONE


@pytest.fixture
def sample_html_document() -> str:
    return sd.SAMPLE_HTML_MINIMAL


@pytest.fixture
def sample_job_create_body() -> dict:
    return sd.sample_job_create_body()


@pytest.fixture
def sample_schedule_create_body() -> dict:
    return sd.sample_schedule_create_body()
