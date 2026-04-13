"""Ensure sources.created_by_user_id exists (idempotent).

Revision ID: 007_sources_creator_col
Revises: 006_sources_fc
Create Date: 2026-04-13

Uses PostgreSQL IF NOT EXISTS so this always repairs the table even when
sqlalchemy.inspect mis-detects columns or a prior 006 apply was partial.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007_sources_creator_col"
down_revision: Union[str, Sequence[str], None] = "006_sources_fc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FK = "fk_sources_created_by_user_id_users"


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE sources ADD COLUMN IF NOT EXISTS created_by_user_id UUID"))
    # Literal constraint name (constant); avoids bind-param issues inside DO blocks.
    op.execute(
        sa.text(
            f"""
            DO $body$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = '{_FK}'
                ) THEN
                    ALTER TABLE sources
                    ADD CONSTRAINT {_FK}
                    FOREIGN KEY (created_by_user_id)
                    REFERENCES users(id)
                    ON DELETE SET NULL;
                END IF;
            END
            $body$;
            """
        ),
    )


def downgrade() -> None:
    op.execute(sa.text(f"ALTER TABLE sources DROP CONSTRAINT IF EXISTS {_FK}"))
    op.execute(sa.text("ALTER TABLE sources DROP COLUMN IF EXISTS created_by_user_id"))
