"""Optional schema creation and default admin seed (idempotent)."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select

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
        return
    try:
        await seed_default_admin_async()
    except Exception as exc:
        logger.warning("seed_failed", extra={"event": "seed_failed", "error": str(exc)})
