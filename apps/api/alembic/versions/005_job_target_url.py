"""Add jobs.url for scrape target (denormalized from payload).

Revision ID: 005_job_url
Revises: 004_schedules
Create Date: 2026-04-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_job_url"
down_revision: Union[str, Sequence[str], None] = "004_schedules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("url", sa.Text(), nullable=True))
    op.execute(
        sa.text("UPDATE jobs SET url = COALESCE(url, payload->>'url') WHERE payload IS NOT NULL AND payload ? 'url'")
    )


def downgrade() -> None:
    op.drop_column("jobs", "url")
