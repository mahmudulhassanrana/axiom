"""JWT access-token claims issued by this API."""

from __future__ import annotations

from typing import TypedDict


class AccessTokenClaims(TypedDict):
    """Payload shape for HS256 access tokens (``type=access``)."""

    sub: str
    email: str
    role: str
    org_id: str
    iat: int
    exp: int
    type: str
    iss: str
    aud: str
