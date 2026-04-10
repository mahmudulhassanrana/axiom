"""Deterministic sample values for tests. Import directly or use pytest fixtures from the plugin."""

from __future__ import annotations

import uuid
from typing import Any

# Fixed UUIDs so snapshots and equality checks are stable across runs.
SAMPLE_ORGANIZATION_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
SAMPLE_USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")
SAMPLE_JOB_ID = uuid.UUID("00000000-0000-4000-8000-000000000003")
SAMPLE_SCHEDULE_ID = uuid.UUID("00000000-0000-4000-8000-000000000004")

SAMPLE_URL = "https://example.com/sample-path?x=1"
SAMPLE_CRON_HOURLY = "0 * * * *"
SAMPLE_TIMEZONE = "UTC"

SAMPLE_HTML_MINIMAL = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Sample</title></head>
<body><p>Hello from testkit</p></body>
</html>"""


def sample_job_create_body() -> dict[str, Any]:
    """Typical body for creating a one-off scrape job (shape only; routes may require more fields)."""
    return {
        "url": SAMPLE_URL,
        "engine": "html_requests",
    }


def sample_schedule_create_body() -> dict[str, Any]:
    """Typical body for creating a cron schedule (shape only)."""
    return {
        "name": "test-schedule",
        "cron_expression": SAMPLE_CRON_HOURLY,
        "timezone": SAMPLE_TIMEZONE,
        "payload": sample_job_create_body(),
    }
