"""Add crawl lineage columns to extracted_data (parent/detail URLs, page type, session).

Revision ID: 010_extracted_crawl_lineage
Revises: 009_scrape_engine_extensions
Create Date: 2026-05-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010_extracted_crawl_lineage"
down_revision: Union[str, Sequence[str], None] = "009_scrape_engine_extensions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("extracted_data", sa.Column("parent_url", sa.Text(), nullable=True))
    op.add_column("extracted_data", sa.Column("detail_page_url", sa.Text(), nullable=True))
    op.add_column("extracted_data", sa.Column("page_type", sa.String(length=32), nullable=True))
    op.add_column("extracted_data", sa.Column("crawl_session_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("extracted_data", "crawl_session_id")
    op.drop_column("extracted_data", "page_type")
    op.drop_column("extracted_data", "detail_page_url")
    op.drop_column("extracted_data", "parent_url")
