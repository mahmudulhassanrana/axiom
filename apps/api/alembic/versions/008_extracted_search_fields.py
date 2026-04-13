"""ExtractedData: country, city, published_date + search indexes.

Revision ID: 008_extracted_search
Revises: 007_sources_creator_col
Create Date: 2026-04-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008_extracted_search"
down_revision: Union[str, Sequence[str], None] = "007_sources_creator_col"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("extracted_data", sa.Column("country", sa.String(length=255), nullable=True))
    op.add_column("extracted_data", sa.Column("city", sa.String(length=255), nullable=True))
    op.add_column("extracted_data", sa.Column("published_date", sa.DateTime(timezone=True), nullable=True))

    op.execute(sa.text("UPDATE extracted_data SET country = NULLIF(BTRIM(payload #>> '{metadata,country}'), '')"))
    op.execute(sa.text("UPDATE extracted_data SET city = NULLIF(BTRIM(payload #>> '{metadata,city}'), '')"))

    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_extracted_data_country_lower ON extracted_data (lower(country))"
        ),
    )
    op.execute(
        sa.text("CREATE INDEX IF NOT EXISTS ix_extracted_data_city_lower ON extracted_data (lower(city))"),
    )
    op.create_index("ix_extracted_data_published_date", "extracted_data", ["published_date"], unique=False)
    op.create_index("ix_extracted_data_created_at_br", "extracted_data", ["created_at"], unique=False)

    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_extracted_data_title_trgm ON extracted_data "
            "USING gin (title gin_trgm_ops)"
        ),
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_extracted_data_text_trgm ON extracted_data "
            "USING gin (text_content gin_trgm_ops)"
        ),
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_extracted_data_text_trgm"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_extracted_data_title_trgm"))
    op.drop_index("ix_extracted_data_created_at_br", table_name="extracted_data")
    op.drop_index("ix_extracted_data_published_date", table_name="extracted_data")
    op.execute(sa.text("DROP INDEX IF EXISTS ix_extracted_data_city_lower"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_extracted_data_country_lower"))
    op.drop_column("extracted_data", "published_date")
    op.drop_column("extracted_data", "city")
    op.drop_column("extracted_data", "country")
