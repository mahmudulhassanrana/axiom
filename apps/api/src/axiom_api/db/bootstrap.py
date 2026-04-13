"""Optional schema creation and default admin seed (idempotent)."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select, text

from axiom_api.core.config import get_auto_create_schema, get_seed_default_admin
from axiom_api.core.security import hash_password
from axiom_api.db.base import Base
from axiom_api.db.models.organization import Organization
from axiom_api.db.models.user import User
from axiom_api.db.session import get_async_session, get_engine

logger = logging.getLogger("axiom_api")

ADMIN_EMAIL = "admin@axiom.local"
ADMIN_PASSWORD = "admin123"


async def ensure_schema_async() -> None:
    if not get_auto_create_schema():
        return
    import axiom_api.db.models  # noqa: F401 — register models on metadata

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def ensure_extracted_search_columns_async() -> None:
    """Add ``country`` / ``city`` / ``published_date`` on ``extracted_data`` if missing (ORM + worker)."""
    engine = get_engine()
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("ALTER TABLE extracted_data ADD COLUMN IF NOT EXISTS country VARCHAR(255)"),
            )
            await conn.execute(
                text("ALTER TABLE extracted_data ADD COLUMN IF NOT EXISTS city VARCHAR(255)"),
            )
            await conn.execute(
                text("ALTER TABLE extracted_data ADD COLUMN IF NOT EXISTS published_date TIMESTAMPTZ"),
            )
    except Exception as exc:
        logger.warning(
            "extracted_search_columns_ensure_failed",
            extra={"event": "extracted_search_columns_ensure_failed", "error": str(exc)},
        )


async def ensure_sources_creator_column_async() -> None:
    """Align ``sources`` with ORM when DB predates ``created_by_user_id`` (idempotent)."""
    engine = get_engine()
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("ALTER TABLE sources ADD COLUMN IF NOT EXISTS created_by_user_id UUID"),
            )
            await conn.execute(
                text(
                    """
                    DO $body$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint
                            WHERE conname = 'fk_sources_created_by_user_id_users'
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
    except Exception as exc:
        logger.warning(
            "sources_creator_column_ensure_failed",
            extra={"event": "sources_creator_column_ensure_failed", "error": str(exc)},
        )


async def seed_default_admin_async() -> None:
    if not get_seed_default_admin():
        return

    async with get_async_session() as session:
        result = await session.execute(select(User).where(User.email == ADMIN_EMAIL))
        if result.scalar_one_or_none() is not None:
            return

        org = Organization(
            name="Axiom",
            slug=f"axiom-seed-{uuid.uuid4().hex[:10]}",
        )
        user = User(
            organization=org,
            email=ADMIN_EMAIL,
            password_hash=hash_password(ADMIN_PASSWORD),
            full_name="Administrator",
            role="admin",
            is_active=True,
        )
        session.add(org)
        session.add(user)
        await session.commit()
        logger.info(
            "seed_default_admin_created",
            extra={"event": "seed_default_admin_created", "email": ADMIN_EMAIL},
        )


async def ensure_schema_and_seed() -> None:
    try:
        await ensure_schema_async()
    except Exception as exc:
        logger.warning(
            "schema_create_failed",
            extra={"event": "schema_create_failed", "error": str(exc)},
        )
    await ensure_sources_creator_column_async()
    await ensure_extracted_search_columns_async()
    try:
        await seed_default_admin_async()
    except Exception as exc:
        logger.warning("seed_failed", extra={"event": "seed_failed", "error": str(exc)})
