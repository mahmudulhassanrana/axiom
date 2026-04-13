"""Sources: crawl config, scheduling, creator.

Revision ID: 006_sources_fc
Revises: 005_job_url
Create Date: 2026-04-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006_sources_fc"
down_revision: Union[str, Sequence[str], None] = "005_job_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "sources",
        sa.Column(
            "crawl_type",
            sa.String(length=32),
            nullable=False,
            server_default="single_page",
        ),
    )
    op.add_column(
        "sources",
        sa.Column(
            "allow_external",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "sources",
        sa.Column("max_pages", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "sources",
        sa.Column("delay_min", sa.Float(), nullable=False, server_default="1.5"),
    )
    op.add_column(
        "sources",
        sa.Column("delay_max", sa.Float(), nullable=False, server_default="2.5"),
    )
    op.add_column(
        "sources",
        sa.Column(
            "schedule_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("sources", sa.Column("schedule_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column(
        "sources",
        sa.Column(
            "schedule_paused",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("sources", sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sources", sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "sources",
        sa.Column(
            "scrape_engine",
            sa.String(length=32),
            nullable=False,
            server_default="html_requests",
        ),
    )
    op.add_column(
        "sources",
        sa.Column(
            "include_html",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("sources", sa.Column("sitemap_url", sa.Text(), nullable=True))
    # Idempotent: column/FK/index may already exist (API bootstrap repair or partial apply).
    op.execute(sa.text("ALTER TABLE sources ADD COLUMN IF NOT EXISTS created_by_user_id UUID"))
    op.execute(
        sa.text(
            """
            DO $body$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'fk_sources_created_by_user_id_users'
                ) THEN
                    ALTER TABLE sources
                    ADD CONSTRAINT fk_sources_created_by_user_id_users
                    FOREIGN KEY (created_by_user_id)
                    REFERENCES users(id)
                    ON DELETE SET NULL;
                END IF;
            END
            $body$;
            """
        ),
    )
    op.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_sources_next_run_at ON sources (next_run_at)"),
    )


def downgrade() -> None:
    op.execute(
        sa.text("ALTER TABLE sources DROP CONSTRAINT IF EXISTS fk_sources_created_by_user_id_users"),
    )
    op.execute(sa.text("ALTER TABLE sources DROP COLUMN IF EXISTS created_by_user_id"))
    op.drop_index(op.f("ix_sources_next_run_at"), table_name="sources")
    op.drop_column("sources", "sitemap_url")
    op.drop_column("sources", "include_html")
    op.drop_column("sources", "scrape_engine")
    op.drop_column("sources", "last_run_at")
    op.drop_column("sources", "next_run_at")
    op.drop_column("sources", "schedule_paused")
    op.drop_column("sources", "schedule_config")
    op.drop_column("sources", "schedule_enabled")
    op.drop_column("sources", "delay_max")
    op.drop_column("sources", "delay_min")
    op.drop_column("sources", "max_pages")
    op.drop_column("sources", "allow_external")
    op.drop_column("sources", "crawl_type")
    op.drop_column("sources", "description")
