"""Job schedules for recurring cron runs.

Revision ID: 004_schedules
Revises: 003_audit
Create Date: 2026-04-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004_schedules"
down_revision: Union[str, Sequence[str], None] = "003_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("cron_expression", sa.String(length=128), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default=sa.text("'UTC'")),
        sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_job_schedules_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_job_schedules_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_schedules")),
    )
    op.create_index(op.f("ix_job_schedules_next_run_at"), "job_schedules", ["next_run_at"], unique=False)
    op.create_index(op.f("ix_job_schedules_organization_id"), "job_schedules", ["organization_id"], unique=False)
    op.create_index(op.f("ix_job_schedules_paused"), "job_schedules", ["paused"], unique=False)

    op.add_column(
        "jobs",
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_jobs_schedule_id_job_schedules"),
        "jobs",
        "job_schedules",
        ["schedule_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_jobs_schedule_id"), "jobs", ["schedule_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_jobs_schedule_id"), table_name="jobs")
    op.drop_constraint(op.f("fk_jobs_schedule_id_job_schedules"), "jobs", type_="foreignkey")
    op.drop_column("jobs", "schedule_id")

    op.drop_index(op.f("ix_job_schedules_paused"), table_name="job_schedules")
    op.drop_index(op.f("ix_job_schedules_organization_id"), table_name="job_schedules")
    op.drop_index(op.f("ix_job_schedules_next_run_at"), table_name="job_schedules")
    op.drop_table("job_schedules")
