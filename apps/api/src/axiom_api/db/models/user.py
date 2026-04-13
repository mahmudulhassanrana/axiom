from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from axiom_api.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from axiom_api.db.models.api_key import ApiKey
    from axiom_api.db.models.job_schedule import JobSchedule
    from axiom_api.db.models.organization import Organization
    from axiom_api.db.models.source import Source


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hashed_password = synonym("password_hash")
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="user", index=True)

    organization: Mapped["Organization"] = relationship(back_populates="users")
    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    job_schedules_created: Mapped[list["JobSchedule"]] = relationship(back_populates="created_by")
    sources_created: Mapped[list["Source"]] = relationship(back_populates="created_by")
