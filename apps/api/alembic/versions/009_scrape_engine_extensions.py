"""Scrape engine: job restriction flag + extracted_data denormalized asset/entity columns.

Revision ID: 009_scrape_engine_extensions
Revises: 008_extracted_search
Create Date: 2026-04-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009_scrape_engine_extensions"
down_revision: Union[str, Sequence[str], None] = "008_extracted_search"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "is_restricted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("extracted_data", sa.Column("images", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column(
        "extracted_data",
        sa.Column("file_links", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "extracted_data",
        sa.Column("structured_entities", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("extracted_data", sa.Column("extraction_type", sa.String(length=32), nullable=True))
    op.add_column("extracted_data", sa.Column("crawl_depth", sa.Integer(), nullable=True))
    op.add_column(
        "extracted_data",
        sa.Column(
            "is_restricted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("extracted_data", "is_restricted")
    op.drop_column("extracted_data", "crawl_depth")
    op.drop_column("extracted_data", "extraction_type")
    op.drop_column("extracted_data", "structured_entities")
    op.drop_column("extracted_data", "file_links")
    op.drop_column("extracted_data", "images")
    op.drop_column("jobs", "is_restricted")
