from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, computed_field, field_validator, model_validator

from axiom_api.schemas.limits import MAX_URL_CHARS
from axiom_api.types.json import JSONValue


class ScrapeJobPayload(BaseModel):
    """Stored on ``Job.payload`` for scrape jobs."""

    model_config = ConfigDict(extra="ignore")

    url: str
    engine: Literal["html_requests", "playwright"] = "html_requests"
    include_html: bool = False
    crawl_max_pages: int = Field(default=1, ge=1, le=50)
    crawl_delay_seconds: float = Field(default=1.5, ge=0.5, le=10.0)
    crawl_jitter_seconds: float = Field(default=0.5, ge=0.0, le=5.0)
    crawl_allow_external: bool = False
    crawl_max_external_pages: int = Field(default=25, ge=0, le=50)
    crawl_max_external_per_host: int = Field(default=5, ge=1, le=20)
    pre_fetch_jitter_max_seconds: float = Field(default=0.0, ge=0.0, le=2.0)
    crawl_type: Literal["single_page", "multi_page", "sitemap"] | None = None
    sitemap_url: str | None = None
    robots_override: bool = False


class JobCreateRequest(BaseModel):
    url: HttpUrl | None = None

    @field_validator("url", mode="before")
    @classmethod
    def _limit_url_length(cls, v: object) -> object:
        if v is None or v == "":
            return None
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
    crawl_max_pages: int = Field(
        default=1,
        ge=1,
        le=50,
        description="Total crawl budget (same host + optional external); 1 = single page only.",
    )
    crawl_delay_seconds: float = Field(
        default=1.5,
        ge=0.5,
        le=10.0,
        description="Base delay between crawl requests (seconds).",
    )
    crawl_jitter_seconds: float = Field(
        default=0.5,
        ge=0.0,
        le=5.0,
        description="Random extra delay 0..jitter added between crawl requests.",
    )
    crawl_allow_external: bool = Field(
        default=False,
        description="When true, may follow off-domain links within external page/host caps.",
    )
    crawl_max_external_pages: int = Field(
        default=25,
        ge=0,
        le=50,
        description="Max external URLs to enqueue (not total site-wide).",
    )
    crawl_max_external_per_host: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Max external URLs per off-domain host to enqueue.",
    )
    pre_fetch_jitter_max_seconds: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Random delay 0..max before each fetch (seconds); 0 disables.",
    )
    crawl_type: Literal["single_page", "multi_page", "sitemap"] | None = Field(
        default=None,
        description="When set with url (no source), selects crawl mode for the worker.",
    )
    sitemap_url: HttpUrl | None = Field(
        default=None,
        description="Optional sitemap URL when crawl_type is sitemap.",
    )
    robots_override: bool = Field(
        default=False,
        description="Requires COMPLIANCE_ROBOTS_OVERRIDE_ENABLED; skips robots.txt when true (audited).",
    )

    @field_validator("sitemap_url", mode="before")
    @classmethod
    def _limit_sitemap_url(cls, v: object) -> object:
        if v is None or v == "":
            return None
        if isinstance(v, str) and len(v) > MAX_URL_CHARS:
            msg = f"sitemap_url must be at most {MAX_URL_CHARS} characters"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def _url_or_source(self) -> Self:
        if self.url is None and self.source_id is None:
            raise ValueError("Provide url and/or source_id (at least one required).")
        return self


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
    country: str | None = None
    city: str | None = None
    published_date: datetime | None = None
    payload: dict[str, JSONValue]
    extractor_kind: str
    http_status: int | None
    created_at: datetime
    page_url: str | None = None
    images: list[dict[str, JSONValue]] = Field(default_factory=list)
    files: list[dict[str, JSONValue]] = Field(default_factory=list)
    full_text: str | None = None
    headings: list[JSONValue] = Field(default_factory=list)
    internal_links: list[dict[str, JSONValue]] = Field(default_factory=list)
    external_links: list[dict[str, JSONValue]] = Field(default_factory=list)
    crawl_source: str | None = None
    content_quality_score: float | None = None
    file_links: list[dict[str, JSONValue]] = Field(default_factory=list)
    structured_entities: dict[str, JSONValue] = Field(default_factory=dict)
    extraction_type: str | None = None

    model_config = {"from_attributes": True}

    @staticmethod
    def _enrich_from_metadata(pl: dict[str, Any], base: dict[str, Any]) -> None:
        meta = pl.get("metadata")
        if not isinstance(meta, dict):
            return
        if base.get("full_text") is None and isinstance(meta.get("full_text"), str):
            base["full_text"] = meta["full_text"]
        if not base.get("headings") and isinstance(meta.get("headings"), list):
            base["headings"] = meta["headings"]
        if not base.get("internal_links") and isinstance(meta.get("internal_links"), list):
            base["internal_links"] = meta["internal_links"]
        if not base.get("external_links") and isinstance(meta.get("external_links"), list):
            base["external_links"] = meta["external_links"]
        if base.get("crawl_source") is None and isinstance(meta.get("crawl_source"), str):
            base["crawl_source"] = meta["crawl_source"]
        if base.get("content_quality_score") is None and isinstance(
            meta.get("content_quality_score"),
            (int, float),
        ):
            base["content_quality_score"] = float(meta["content_quality_score"])
        if base.get("country") is None and isinstance(meta.get("country"), str):
            base["country"] = meta["country"]
        if base.get("city") is None and isinstance(meta.get("city"), str):
            base["city"] = meta["city"]

    @model_validator(mode="before")
    @classmethod
    def _assets_from_payload(cls, data: object) -> object:
        if isinstance(data, dict):
            d = dict(data)
            pl = d.get("payload")
            if isinstance(pl, dict):
                if d.get("page_url") is None:
                    d["page_url"] = pl.get("page_url") if isinstance(pl.get("page_url"), str) else d.get("source_url")
                if not d.get("images"):
                    d["images"] = pl.get("images") if isinstance(pl.get("images"), list) else []
                if not d.get("files"):
                    d["files"] = pl.get("files") if isinstance(pl.get("files"), list) else []
                if not d.get("file_links"):
                    fl = pl.get("file_links") if isinstance(pl.get("file_links"), list) else None
                    d["file_links"] = fl if fl is not None else list(d.get("files") or [])
                if not d.get("structured_entities") and isinstance(pl.get("structured_entities"), dict):
                    d["structured_entities"] = pl["structured_entities"]
                elif not d.get("structured_entities"):
                    d["structured_entities"] = {}
                if d.get("extraction_type") is None:
                    d["extraction_type"] = pl.get("extraction_type") if isinstance(pl.get("extraction_type"), str) else None
                cls._enrich_from_metadata(pl, d)
            if d.get("full_text") is None and isinstance(d.get("text_content"), str):
                d["full_text"] = d["text_content"]
            return d
        if not hasattr(data, "payload"):
            return data
        pl = data.payload
        if not isinstance(pl, dict):
            pl = {}
        page_url = pl.get("page_url") if isinstance(pl.get("page_url"), str) else None
        imgs = pl.get("images") if isinstance(pl.get("images"), list) else []
        files = pl.get("files") if isinstance(pl.get("files"), list) else []
        flinks = pl.get("file_links") if isinstance(pl.get("file_links"), list) else files
        struct_e = pl.get("structured_entities") if isinstance(pl.get("structured_entities"), dict) else {}
        ext_t = getattr(data, "extraction_type", None) or (
            pl.get("extraction_type") if isinstance(pl.get("extraction_type"), str) else None
        )
        col_fl = getattr(data, "file_links", None)
        col_se = getattr(data, "structured_entities", None)
        if isinstance(col_fl, list) and col_fl:
            flinks = col_fl
        if isinstance(col_se, dict) and col_se:
            struct_e = col_se
        out: dict[str, Any] = {
            "id": data.id,
            "run_id": data.run_id,
            "source_url": data.source_url,
            "final_url": data.final_url,
            "title": data.title,
            "text_content": data.text_content,
            "country": getattr(data, "country", None),
            "city": getattr(data, "city", None),
            "published_date": getattr(data, "published_date", None),
            "payload": data.payload,
            "extractor_kind": data.extractor_kind,
            "http_status": data.http_status,
            "created_at": data.created_at,
            "page_url": page_url or data.source_url,
            "images": imgs,
            "files": files,
            "file_links": flinks,
            "structured_entities": struct_e,
            "extraction_type": ext_t,
            "full_text": None,
            "headings": [],
            "internal_links": [],
            "external_links": [],
            "crawl_source": None,
            "content_quality_score": None,
        }
        cls._enrich_from_metadata(pl, out)
        if out.get("full_text") is None and isinstance(data.text_content, str):
            out["full_text"] = data.text_content
        return out


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

    @computed_field
    @property
    def is_restricted(self) -> bool:
        return self.status == "restricted"


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
