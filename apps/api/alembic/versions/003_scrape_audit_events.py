"""Scrape audit events table.

Revision ID: 003_audit
Revises: 002_auth
Create Date: 2026-04-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_audit"
down_revision: Union[str, Sequence[str], None] = "002_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scrape_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("engine", sa.String(length=32), nullable=True),
        sa.Column("step", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=128), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_scrape_audit_events_organization_id_organizations"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_scrape_audit_events_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scrape_audit_events")),
    )
    op.create_index(
        op.f("ix_scrape_audit_events_correlation_id"),
        "scrape_audit_events",
        ["correlation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scrape_audit_events_host"),
        "scrape_audit_events",
        ["host"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_scrape_audit_events_host"), table_name="scrape_audit_events")
    op.drop_index(op.f("ix_scrape_audit_events_correlation_id"), table_name="scrape_audit_events")
    op.drop_table("scrape_audit_events")
