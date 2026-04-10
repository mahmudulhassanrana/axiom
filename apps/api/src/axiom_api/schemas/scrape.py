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

    model_config = {"populate_by_name": True}


class ScrapeQueuedResponse(BaseModel):
    status: Literal["queued"] = "queued"
    task_id: str
    message: str = Field(
        default="Job accepted by Celery. Use task_id with the result backend or a future task-status endpoint.",
    )
