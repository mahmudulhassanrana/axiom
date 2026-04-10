from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine, pool

from axiom_api.core.config import get_sync_database_url
from axiom_api.db.base import Base

import axiom_api.db.models  # noqa: F401

target_metadata = Base.metadata


def get_url() -> str:
    return get_sync_database_url()


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(get_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
