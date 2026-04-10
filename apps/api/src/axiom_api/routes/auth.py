from __future__ import annotations

import uuid
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from axiom_api.core.security import (
    api_key_prefix,
    create_access_token,
    generate_api_key_raw,
    hash_api_key,
    hash_password,
    verify_password,
)
from axiom_api.db.deps import get_db
from axiom_api.db.models.api_key import ApiKey
from axiom_api.db.models.organization import Organization
from axiom_api.db.models.user import User
from axiom_api.deps.auth import get_current_user
from axiom_api.schemas.auth import (
    ApiKeyCreatedResponse,
    ApiKeyCreateRequest,
    ApiKeyPublic,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserPublic,
)

router = APIRouter(prefix="/auth", tags=["auth"])


async def _allocate_unique_org_slug(session: AsyncSession) -> str:
    for _ in range(32):
        candidate = f"org-{uuid.uuid4().hex[:12]}"
        r = await session.execute(select(Organization.id).where(Organization.slug == candidate))
        if r.scalar_one_or_none() is None:
            return candidate
    raise HTTPException(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Could not allocate organization slug",
    )


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register",
    description="Create organization and first admin user; returns JWT.",
)
async def register(
    body: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RegisterResponse:
    email_norm = str(body.email).lower().strip()
    org_name = (body.organization_name or "").strip() or f"{email_norm.split('@')[0]} workspace"
    org_slug = body.organization_slug if body.organization_slug else await _allocate_unique_org_slug(session)
    org = Organization(name=org_name, slug=org_slug)
    user = User(
        organization=org,
        email=email_norm,
        password_hash=hash_password(body.password),
        full_name=body.full_name.strip() if body.full_name else None,
        role="admin",
        is_active=True,
    )
    session.add(org)
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Email or organization slug already registered",
        ) from exc
    except OperationalError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Database unavailable. Start PostgreSQL and set DATABASE_URL "
                "(e.g. load the repo root .env or apps/api/.env before uvicorn)."
            ),
        ) from exc
    try:
        await session.refresh(user)
    except OperationalError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Database unavailable. Start PostgreSQL and set DATABASE_URL "
                "(e.g. load the repo root .env or apps/api/.env before uvicorn)."
            ),
        ) from exc
    token, exp = create_access_token(
        subject_user_id=user.id,
        email=user.email,
        role=user.role,
        organization_id=user.organization_id,
    )
    return RegisterResponse(
        user=UserPublic.model_validate(user),
        access_token=token,
        token_type="bearer",
        expires_in=exp,
    )


@router.post("/login", response_model=TokenResponse, summary="Login", description="Email/password; returns JWT access token.")
async def login(
    body: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    result = await session.execute(select(User).where(User.email == str(body.email).lower().strip()))
    user = result.scalar_one_or_none()
    if user is None or user.password_hash is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    token, exp = create_access_token(
        subject_user_id=user.id,
        email=user.email,
        role=user.role,
        organization_id=user.organization_id,
    )
    return TokenResponse(access_token=token, token_type="bearer", expires_in=exp)


@router.get("/me", response_model=UserPublic, summary="Current user", description="Requires Bearer JWT or API key.")
async def me(current: Annotated[User, Depends(get_current_user)]) -> User:
    return current


@router.post("/api-keys", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: ApiKeyCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> ApiKeyCreatedResponse:
    raw = generate_api_key_raw()
    key = ApiKey(
        user_id=current.id,
        name=body.name.strip() if body.name else None,
        key_hash=hash_api_key(raw),
        key_prefix=api_key_prefix(raw),
        is_active=True,
    )
    session.add(key)
    await session.flush()
    return ApiKeyCreatedResponse(
        id=key.id,
        name=key.name,
        key_prefix=key.key_prefix,
        key=raw,
    )


@router.get("/api-keys", response_model=list[ApiKeyPublic])
async def list_api_keys(
    session: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> list[ApiKey]:
    result = await session.execute(
        select(ApiKey).where(ApiKey.user_id == current.id).order_by(ApiKey.created_at.desc()),
    )
    return list(result.scalars().all())


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current: Annotated[User, Depends(get_current_user)],
) -> None:
    result = await session.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == current.id),
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="API key not found")
    row.is_active = False
    await session.flush()
