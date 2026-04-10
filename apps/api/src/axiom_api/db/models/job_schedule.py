from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from axiom_api.db.base import Base, TimestampMixin
from axiom_api.types.json import JSONValue

if TYPE_CHECKING:
    from axiom_api.db.models.job import Job
    from axiom_api.db.models.organization import Organization
    from axiom_api.db.models.user import User


class JobSchedule(Base, TimestampMixin):
    """Recurring scrape definition (cron). Celery Beat drives `tick_schedules` to enqueue runs."""

    __tablename__ = "job_schedules"

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
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cron_expression: Mapped[str] = mapped_column(String(128), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    payload: Mapped[dict[str, JSONValue]] = mapped_column(JSONB, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped["Organization"] = relationship(back_populates="job_schedules")
    created_by: Mapped["User | None"] = relationship(back_populates="job_schedules_created")
    jobs: Mapped[list["Job"]] = relationship(back_populates="schedule")
