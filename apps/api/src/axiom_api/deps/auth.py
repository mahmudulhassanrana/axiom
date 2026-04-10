from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom_api.core.security import decode_access_token, hash_api_key
from axiom_api.db.deps import get_db
from axiom_api.db.models.api_key import ApiKey
from axiom_api.db.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)
bearer_scheme_required = HTTPBearer(auto_error=True)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _user_from_jwt(session: AsyncSession, token: str) -> User:
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc
    if payload["type"] != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    try:
        uid = UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject") from exc
    result = await session.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


async def _user_from_api_key(session: AsyncSession, raw_key: str) -> User:
    digest = hash_api_key(raw_key.strip())
    result = await session.execute(
        select(ApiKey).where(ApiKey.key_hash == digest, ApiKey.is_active.is_(True)),
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    u_result = await session.execute(select(User).where(User.id == row.user_id))
    user = u_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    row.last_used_at = datetime.now(UTC)
    await session.flush()
    return user


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_db)],
    bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    x_api_key: Annotated[str | None, Depends(api_key_header)],
) -> User:
    if bearer is not None and bearer.scheme.lower() == "bearer":
        return await _user_from_jwt(session, bearer.credentials)
    if x_api_key:
        return await _user_from_api_key(session, x_api_key)
    raise HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required (Bearer token or X-API-Key)",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user_bearer(
    session: Annotated[AsyncSession, Depends(get_db)],
    bearer: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme_required)],
) -> User:
    """Resolve user from ``Authorization: Bearer <JWT>`` only (no API key)."""
    if bearer.scheme.lower() != "bearer":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _user_from_jwt(session, bearer.credentials)


def require_roles(*allowed: str):
    async def _dep(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return _dep


RequireAdmin = Annotated[User, Depends(require_roles("admin"))]
