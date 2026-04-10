from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator

from axiom_api.schemas.limits import MAX_URL_CHARS


class SchedulePayload(BaseModel):
    """Same scrape parameters as a one-off job."""

    url: HttpUrl

    @field_validator("url", mode="before")
    @classmethod
    def _limit_url_length(cls, v: object) -> object:
        if isinstance(v, str) and len(v) > MAX_URL_CHARS:
            msg = f"URL must be at most {MAX_URL_CHARS} characters"
            raise ValueError(msg)
        return v

    engine: Literal["html_requests", "playwright"] = "html_requests"
    include_html: bool = False
    source_id: UUID | None = None


class ScheduleCreateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    cron_expression: str = Field(
        min_length=9,
        max_length=128,
        description="Standard 5-field cron in UTC (e.g. '0 * * * *' hourly).",
    )
    timezone: str = Field(default="UTC", max_length=64, description="Reserved for future use; evaluated in UTC today.")
    payload: SchedulePayload
    max_retries: int = Field(default=5, ge=0, le=50)


class ScheduleUpdateRequest(BaseModel):
    paused: bool | None = None
    name: str | None = Field(default=None, max_length=255)


class SchedulePublic(BaseModel):
    id: UUID
    organization_id: UUID
    created_by_user_id: UUID | None
    name: str | None
    cron_expression: str
    timezone: str
    paused: bool
    payload: SchedulePayload
    max_retries: int
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
