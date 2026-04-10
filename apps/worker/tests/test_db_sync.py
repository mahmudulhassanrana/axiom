"""Worker DSN normalization matches API sync URL expectations for psycopg."""

from axiom_worker.db_sync import normalize_postgres_url_for_psycopg


def test_normalize_asyncpg_driver_stripped() -> None:
    u = "postgresql+asyncpg://u:p@localhost:5432/db"
    assert normalize_postgres_url_for_psycopg(u) == "postgresql://u:p@localhost:5432/db"


def test_normalize_psycopg_driver_stripped() -> None:
    u = "postgresql+psycopg://u:p@localhost:5432/db"
    assert normalize_postgres_url_for_psycopg(u) == "postgresql://u:p@localhost:5432/db"


def test_plain_postgresql_unchanged() -> None:
    u = "postgresql://u:p@localhost:5432/db"
    assert normalize_postgres_url_for_psycopg(u) == u
