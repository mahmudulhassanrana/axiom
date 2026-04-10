from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID

import bcrypt
import jwt

from axiom_api.core.config import (
    get_access_token_expire_minutes,
    get_api_key_pepper,
    get_jwt_audience,
    get_jwt_issuer,
    get_jwt_secret_key,
)
from axiom_api.types.jwt import AccessTokenClaims

JWT_ALGORITHM = "HS256"


def hash_password(plain: str) -> str:
    digest = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())
    return digest.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    *,
    subject_user_id: UUID,
    email: str,
    role: str,
    organization_id: UUID,
) -> tuple[str, int]:
    """Return (token, expires_in_seconds)."""
    now = datetime.now(UTC)
    expire_minutes = get_access_token_expire_minutes()
    exp = now + timedelta(minutes=expire_minutes)
    payload: AccessTokenClaims = {
        "sub": str(subject_user_id),
        "email": email,
        "role": role,
        "org_id": str(organization_id),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "type": "access",
        "iss": get_jwt_issuer(),
        "aud": get_jwt_audience(),
    }
    token = jwt.encode(payload, get_jwt_secret_key(), algorithm=JWT_ALGORITHM)
    return token, expire_minutes * 60


def decode_access_token(token: str) -> AccessTokenClaims:
    raw = jwt.decode(
        token,
        get_jwt_secret_key(),
        algorithms=[JWT_ALGORITHM],
        audience=get_jwt_audience(),
        issuer=get_jwt_issuer(),
        options={"require": ["exp", "iat", "sub"]},
        leeway=10,
    )
    return cast(AccessTokenClaims, raw)


def generate_api_key_raw() -> str:
    return "axk_" + secrets.token_urlsafe(32)


def hash_api_key(raw_key: str) -> str:
    peppered = (raw_key + get_api_key_pepper()).encode()
    return hashlib.sha256(peppered).hexdigest()


def api_key_prefix(raw_key: str) -> str:
    return raw_key[:12] if len(raw_key) >= 12 else raw_key
