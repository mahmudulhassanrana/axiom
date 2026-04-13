from __future__ import annotations

import logging
from datetime import datetime, time, timezone
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from axiom_api.db.deps import get_db
from axiom_api.db.models.user import User
from axiom_api.deps.auth import get_current_user_bearer
from axiom_api.schemas.search import SearchResponse
from axiom_api.services.extracted_search import search_extracted

router = APIRouter(prefix="/search", tags=["search"])
logger = logging.getLogger("axiom_api.search")


def _normalize_optional_str(value: str | None) -> str | None:
    if value is None:
        return None
    s = value.strip()
    return s or None


def _parse_uuid_optional(value: str | None) -> UUID | None:
    if not value or not str(value).strip():
        return None
    try:
        return UUID(str(value).strip())
    except ValueError:
        return None


def _parse_date_filter(value: str | None, *, end_of_day: bool = False) -> datetime | None:
    """Parse query date string; return None if missing or invalid (ignored filter)."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        elif len(s) == 10 and s[4] == "-" and s[7] == "-":
            d = datetime.fromisoformat(s).date()
            if end_of_day:
                dt = datetime.combine(d, time(23, 59, 59, 999999), tzinfo=timezone.utc)
            else:
                dt = datetime.combine(d, time.min, tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@router.get(
    "",
    response_model=SearchResponse,
    summary="Advanced search over extracted scrape data",
)
async def search_extracted_data(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_bearer)],
    keyword: str | None = Query(default=None, max_length=500),
    country: str | None = Query(default=None, max_length=255),
    city: str | None = Query(default=None, max_length=255),
    date_from: str | None = Query(default=None, max_length=80),
    date_to: str | None = Query(default=None, max_length=80),
    job_id: str | None = Query(default=None, max_length=36),
    source_id: str | None = Query(default=None, max_length=36),
    page: int = Query(default=1, ge=1, le=10_000),
    limit: int = Query(default=20, ge=1, le=100),
    sort: Literal["newest", "oldest"] = Query(default="newest"),
) -> SearchResponse:
    kw = _normalize_optional_str(keyword)
    co = _normalize_optional_str(country)
    ci = _normalize_optional_str(city)
    j_uuid = _parse_uuid_optional(job_id)
    s_uuid = _parse_uuid_optional(source_id)

    df = _parse_date_filter(date_from, end_of_day=False)
    dt = _parse_date_filter(date_to, end_of_day=True)

    if df is not None and dt is not None and dt < df:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_to must be >= date_from",
        )

    logger.info(
        "search.request",
        extra={
            "raw_keyword": keyword,
            "raw_country": country,
            "raw_city": city,
            "raw_date_from": date_from,
            "raw_date_to": date_to,
            "raw_job_id": job_id,
            "raw_source_id": source_id,
            "normalized_keyword": kw,
            "normalized_country": co,
            "normalized_city": ci,
            "parsed_date_from": df.isoformat() if df else None,
            "parsed_date_to": dt.isoformat() if dt else None,
            "job_id": str(j_uuid) if j_uuid else None,
            "source_id": str(s_uuid) if s_uuid else None,
            "page": page,
            "limit": limit,
            "sort": sort,
        },
    )

    return await search_extracted(
        session,
        organization_id=user.organization_id,
        keyword=kw,
        country=co,
        city=ci,
        date_from=df,
        date_to=dt,
        job_id=j_uuid,
        source_id=s_uuid,
        page=page,
        limit=limit,
        sort=sort,
    )
