"""OpenAPI tag metadata (kept out of ``app.py`` for clarity)."""

from __future__ import annotations

from typing import TypedDict


class OpenAPITag(TypedDict):
    name: str
    description: str


OPENAPI_TAGS: list[OpenAPITag] = [
    {"name": "health", "description": "Liveness and operational probes."},
    {"name": "meta", "description": "Service identity and version."},
    {
        "name": "scrape",
        "description": (
            "URL extraction with compliance (robots.txt, domain lists, Redis per-domain limits, "
            "delay+jitter) and audit logging."
        ),
    },
    {"name": "jobs", "description": "Scrape jobs and runs (queued Celery tasks with audit logs)."},
    {
        "name": "search",
        "description": "Advanced search across persisted extracted pages (keyword, location, date range).",
    },
    {
        "name": "sources",
        "description": "Reusable scrape targets (URLs, crawl settings, optional Celery Beat schedules).",
    },
    {"name": "runs", "description": "Run details including persisted extracted text and links."},
    {"name": "exports", "description": "Download ExtractedDocument payloads as JSON, CSV, Markdown, or HTML."},
    {
        "name": "schedules",
        "description": "Cron job schedules (pause/resume); immediate runs use POST /jobs.",
    },
    {"name": "auth", "description": "JWT login/register and API keys (X-API-Key or Authorization: Bearer)."},
    {"name": "admin", "description": "Organization admin operations (requires role=admin)."},
]
