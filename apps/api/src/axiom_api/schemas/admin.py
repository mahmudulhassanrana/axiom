from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from axiom_api.core.password_policy import StrongPassword


class AdminCreateUserRequest(BaseModel):
    email: EmailStr
    password: StrongPassword
    role: Literal["admin", "user"] = "user"
    full_name: str | None = Field(default=None, max_length=255)


class AdminStatsResponse(BaseModel):
    total_jobs: int
    by_status: dict[str, int]
    failed_jobs: int


class ComplianceDomainsResponse(BaseModel):
    blocklist: list[str]
    allowlist: list[str]
