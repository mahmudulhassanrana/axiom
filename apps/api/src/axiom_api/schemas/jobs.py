from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, computed_field, field_validator

from axiom_api.schemas.limits import MAX_URL_CHARS
from axiom_api.types.json import JSONValue


class ScrapeJobPayload(BaseModel):
    """Stored on ``Job.payload`` for scrape jobs."""

    model_config = ConfigDict(extra="ignore")

    url: str
    engine: Literal["html_requests", "playwright"] = "html_requests"
    include_html: bool = False


class JobCreateRequest(BaseModel):
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
    max_retries: int = Field(
        default=3,
        ge=0,
        le=50,
        description="Celery task retries for transient fetch errors (default 3).",
    )


class RunPublic(BaseModel):
    id: UUID
    job_id: UUID
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    metrics: dict[str, JSONValue] | None

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def finished_at(self) -> datetime | None:
        return self.completed_at


class ExtractedDataPublic(BaseModel):
    id: UUID
    run_id: UUID
    source_url: str
    final_url: str | None
    title: str | None
    text_content: str | None
    payload: dict[str, JSONValue]
    extractor_kind: str
    http_status: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RunDetailPublic(RunPublic):
    extracted_data: list[ExtractedDataPublic] = Field(default_factory=list)



class JobPublic(BaseModel):
    id: UUID
    organization_id: UUID
    source_id: UUID | None
    schedule_id: UUID | None = None
    kind: str
    url: str | None = None
    status: str
    celery_task_id: str | None
    payload: ScrapeJobPayload | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobDetailPublic(JobPublic):
    runs: list[RunDetailPublic] = Field(default_factory=list)


class AuditLogEntryPublic(BaseModel):
    id: UUID
    created_at: datetime
    source: str
    url: str
    host: str
    engine: str | None
    step: str
    outcome: str
    http_status: int | None
    error_message: str | None
    celery_task_id: str | None
    extra: dict[str, JSONValue] | None

    model_config = {"from_attributes": True}
