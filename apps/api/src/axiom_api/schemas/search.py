from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SearchHit(BaseModel):
    id: UUID
    run_id: UUID
    job_id: UUID
    source_id: UUID | None = None
    page_url: str
    title: str | None
    preview: str
    created_at: datetime
    published_date: datetime | None
    country: str | None
    city: str | None


class SearchResponse(BaseModel):
    items: list[SearchHit] = Field(default_factory=list)
    total: int
    page: int
    limit: int
    sort: Literal["newest", "oldest"] = "newest"
