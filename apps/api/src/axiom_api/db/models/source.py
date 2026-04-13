from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from axiom_api.db.base import Base, TimestampMixin
from axiom_api.types.json import JSONValue

if TYPE_CHECKING:
    from axiom_api.db.models.job import Job
    from axiom_api.db.models.organization import Organization
    from axiom_api.db.models.user import User


class Source(Base, TimestampMixin):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="http")
    crawl_type: Mapped[str] = mapped_column(String(32), nullable=False, default="single_page")
    allow_external: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    delay_min: Mapped[float] = mapped_column(Float, nullable=False, default=1.5)
    delay_max: Mapped[float] = mapped_column(Float, nullable=False, default=2.5)
    scrape_engine: Mapped[str] = mapped_column(String(32), nullable=False, default="html_requests")
    include_html: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sitemap_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    schedule_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    schedule_config: Mapped[dict[str, JSONValue] | None] = mapped_column(JSONB, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    config: Mapped[dict[str, JSONValue] | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    organization: Mapped["Organization"] = relationship(back_populates="sources")
    created_by: Mapped["User | None"] = relationship(back_populates="sources_created")
    jobs: Mapped[list["Job"]] = relationship(back_populates="source")
