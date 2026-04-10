from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from axiom_api.db.base import Base, TimestampMixin
from axiom_api.types.json import JSONValue

if TYPE_CHECKING:
    from axiom_api.db.models.run import Run


class ExtractedData(Base, TimestampMixin):
    """
    Persisted output of an extraction (e.g. axiom_extractors.ExtractedDocument as JSON).
    """

    __tablename__ = "extracted_data"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    final_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, JSONValue]] = mapped_column(JSONB, nullable=False)
    extractor_kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)

    run: Mapped["Run"] = relationship(back_populates="extracted_data")
