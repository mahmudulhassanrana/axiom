from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    organization_name: str | None = Field(default=None, max_length=255)
    organization_slug: str | None = Field(default=None, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)

    @field_validator("organization_slug")
    @classmethod
    def slug_format(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip().lower()
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
        if not all(c in allowed for c in s):
            msg = "Slug may only contain lowercase letters, digits, and hyphens"
            raise ValueError(msg)
        if s.startswith("-") or s.endswith("-") or "--" in s:
            msg = "Slug must not start/end with hyphen or contain consecutive hyphens"
            raise ValueError(msg)
        return s


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class UserPublic(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    role: Literal["admin", "user"]
    organization_id: UUID
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RegisterResponse(BaseModel):
    user: UserPublic
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class ApiKeyCreateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=128)


class ApiKeyPublic(BaseModel):
    id: UUID
    name: str | None
    key_prefix: str
    is_active: bool

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(BaseModel):
    id: UUID
    name: str | None
    key_prefix: str
    key: str = Field(description="Shown only once. Store it securely.")
