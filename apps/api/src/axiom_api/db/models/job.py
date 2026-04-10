from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from axiom_api.db.base import Base, TimestampMixin
from axiom_api.types.json import JSONValue

if TYPE_CHECKING:
    from axiom_api.db.models.job_schedule import JobSchedule
    from axiom_api.db.models.organization import Organization
    from axiom_api.db.models.run import Run
    from axiom_api.db.models.source import Source


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

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
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False, default="scrape")
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    payload: Mapped[dict[str, JSONValue] | None] = mapped_column(JSONB, nullable=True)
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_schedules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    organization: Mapped["Organization"] = relationship(back_populates="jobs")
    source: Mapped["Source | None"] = relationship(back_populates="jobs")
    schedule: Mapped["JobSchedule | None"] = relationship(back_populates="jobs")
    runs: Mapped[list["Run"]] = relationship(back_populates="job", cascade="all, delete-orphan")
