from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from axiom_api.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from axiom_api.db.models.job import Job
    from axiom_api.db.models.job_schedule import JobSchedule
    from axiom_api.db.models.source import Source
    from axiom_api.db.models.user import User


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)

    users: Mapped[list["User"]] = relationship(back_populates="organization")
    sources: Mapped[list["Source"]] = relationship(back_populates="organization")
    jobs: Mapped[list["Job"]] = relationship(back_populates="organization")
    job_schedules: Mapped[list["JobSchedule"]] = relationship(back_populates="organization")
