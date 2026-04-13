from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

from axiom_api.schemas.limits import MAX_URL_CHARS


class ScrapeRequest(BaseModel):
    url: HttpUrl

    @field_validator("url", mode="before")
    @classmethod
    def _limit_url_length(cls, v: object) -> object:
        if isinstance(v, str) and len(v) > MAX_URL_CHARS:
            msg = f"URL must be at most {MAX_URL_CHARS} characters"
            raise ValueError(msg)
        return v
    engine: Literal["html_requests", "playwright"] = Field(
        default="html_requests",
        description="html_requests: HTTP + BeautifulSoup. playwright: headless browser render.",
    )
    include_html: bool = Field(
        default=False,
        description="Include raw HTML in the response payload (larger responses).",
    )
    async_execution: bool = Field(
        default=True,
        alias="async",
        description=(
            "If true (default), enqueue `axiom.scrape` on Celery and return 202 + task_id. "
            "If false, run extraction synchronously in the API process (200 + document)."
        ),
    )
    crawl_max_pages: int = Field(default=1, ge=1, le=50)
    crawl_delay_seconds: float = Field(default=1.5, ge=0.5, le=10.0)
    crawl_jitter_seconds: float = Field(default=0.5, ge=0.0, le=5.0)
    crawl_allow_external: bool = False
    crawl_max_external_pages: int = Field(default=25, ge=0, le=50)
    crawl_max_external_per_host: int = Field(default=5, ge=1, le=20)
    pre_fetch_jitter_max_seconds: float = Field(default=0.0, ge=0.0, le=2.0)

    model_config = {"populate_by_name": True}


class ScrapeQueuedResponse(BaseModel):
    status: Literal["queued"] = "queued"
    task_id: str
    message: str = Field(
        default="Job accepted by Celery. Use task_id with the result backend or a future task-status endpoint.",
    )
