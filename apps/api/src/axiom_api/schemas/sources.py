from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from axiom_api.schemas.limits import MAX_URL_CHARS
from axiom_api.types.json import JSONValue


CrawlType = Literal["single_page", "multi_page", "sitemap"]
Engine = Literal["html_requests", "playwright"]
ScheduleType = Literal["cron", "hourly", "daily"]


class ScheduleConfig(BaseModel):
    type: ScheduleType = "cron"
    cron_expression: str | None = Field(default=None, max_length=128)
    timezone: str = Field(default="UTC", max_length=64)

    @model_validator(mode="after")
    def _cron_when_needed(self) -> ScheduleConfig:
        if self.type == "cron":
            expr = (self.cron_expression or "").strip()
            if len(expr) < 9:
                raise ValueError("cron_expression is required when type is cron")
            self.cron_expression = expr
        return self


class SourceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    base_url: HttpUrl
    description: str | None = Field(default=None, max_length=8000)
    crawl_type: CrawlType = "single_page"
    allow_external: bool = False
    max_pages: int = Field(default=1, ge=1, le=50)
    delay_min: float = Field(default=1.5, ge=0.5, le=30.0)
    delay_max: float = Field(default=2.5, ge=0.5, le=30.0)
    scrape_engine: Engine = "html_requests"
    include_html: bool = False
    sitemap_url: HttpUrl | None = None
    schedule_enabled: bool = False
    schedule_paused: bool = False
    schedule_config: ScheduleConfig | None = None
    is_active: bool = True

    @field_validator("base_url", mode="before")
    @classmethod
    def _limit_base(cls, v: object) -> object:
        if isinstance(v, str) and len(v) > MAX_URL_CHARS:
            raise ValueError(f"base_url must be at most {MAX_URL_CHARS} characters")
        return v

    @model_validator(mode="after")
    def _delay_order(self) -> SourceCreateRequest:
        if self.delay_max < self.delay_min:
            raise ValueError("delay_max must be >= delay_min")
        if self.schedule_enabled and self.schedule_config is None:
            raise ValueError("schedule_config is required when schedule_enabled is true")
        return self


class SourceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    base_url: HttpUrl | None = None
    description: str | None = Field(default=None, max_length=8000)
    crawl_type: CrawlType | None = None
    allow_external: bool | None = None
    max_pages: int | None = Field(default=None, ge=1, le=50)
    delay_min: float | None = Field(default=None, ge=0.5, le=30.0)
    delay_max: float | None = Field(default=None, ge=0.5, le=30.0)
    scrape_engine: Engine | None = None
    include_html: bool | None = None
    sitemap_url: HttpUrl | None = None
    schedule_enabled: bool | None = None
    schedule_paused: bool | None = None
    schedule_config: ScheduleConfig | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _delays(self) -> SourceUpdateRequest:
        dmin, dmax = self.delay_min, self.delay_max
        if dmin is not None and dmax is not None and dmax < dmin:
            raise ValueError("delay_max must be >= delay_min")
        return self

    @field_validator("base_url", mode="before")
    @classmethod
    def _limit_base(cls, v: object) -> object:
        if isinstance(v, str) and len(v) > MAX_URL_CHARS:
            raise ValueError(f"base_url must be at most {MAX_URL_CHARS} characters")
        return v


class SourcePublic(BaseModel):
    id: UUID
    organization_id: UUID
    created_by_user_id: UUID | None
    name: str
    base_url: str
    description: str | None
    kind: str
    crawl_type: str
    allow_external: bool
    max_pages: int
    delay_min: float
    delay_max: float
    scrape_engine: str
    include_html: bool
    sitemap_url: str | None
    schedule_enabled: bool
    schedule_paused: bool
    schedule_config: dict[str, JSONValue] | None
    next_run_at: datetime | None
    last_run_at: datetime | None
    config: dict[str, JSONValue] | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SourceDetailPublic(SourcePublic):
    recent_jobs: list[dict[str, JSONValue]] = Field(default_factory=list)


class SourceRunResponse(BaseModel):
    job_id: UUID
    run_id: UUID
    celery_task_id: str | None
    status: str
