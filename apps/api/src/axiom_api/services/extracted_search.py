"""Advanced search over ``extracted_data`` (org-scoped via job)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal, cast
from uuid import UUID

from sqlalchemy import Select, case, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom_api.db.models.extracted_data import ExtractedData
from axiom_api.db.models.job import Job
from axiom_api.db.models.run import Run
from axiom_api.schemas.search import SearchHit, SearchResponse

logger = logging.getLogger("axiom_api.search")


def _escape_ilike(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


def _ilike_pat(term: str) -> str:
    return f"%{_escape_ilike(term.strip())}%"


def _page_url(row: ExtractedData) -> str:
    pl = row.payload if isinstance(row.payload, dict) else {}
    pu = pl.get("page_url")
    if isinstance(pu, str) and pu.strip():
        return pu.strip()
    if row.final_url and str(row.final_url).strip():
        return str(row.final_url).strip()
    return row.source_url


def _preview(text: str | None, limit: int = 280) -> str:
    if not text or not str(text).strip():
        return ""
    s = " ".join(str(text).split())
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _meta_country_expr():
    meta = ExtractedData.payload["metadata"]
    return func.coalesce(ExtractedData.country, meta.op("->>")(literal("country")))


def _meta_city_expr():
    meta = ExtractedData.payload["metadata"]
    return func.coalesce(ExtractedData.city, meta.op("->>")(literal("city")))


def _base_select() -> Select[Any]:
    return (
        select(ExtractedData, Run.job_id, Job.source_id)
        .join(Run, ExtractedData.run_id == Run.id)
        .join(Job, Run.job_id == Job.id)
    )


def _apply_filters(
    stmt: Select[Any],
    *,
    organization_id: UUID,
    keyword: str | None,
    country: str | None,
    city: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    job_id: UUID | None,
    source_id: UUID | None,
) -> Select[Any]:
    stmt = stmt.where(Job.organization_id == organization_id)

    if job_id is not None:
        stmt = stmt.where(Run.job_id == job_id)
    if source_id is not None:
        stmt = stmt.where(Job.source_id == source_id)

    if keyword and keyword.strip():
        pat = _ilike_pat(keyword)
        stmt = stmt.where(
            or_(
                func.coalesce(ExtractedData.title, "").ilike(pat, escape="\\"),
                func.coalesce(ExtractedData.text_content, "").ilike(pat, escape="\\"),
            ),
        )

    if country and country.strip():
        pat = _ilike_pat(country)
        ce = func.coalesce(_meta_country_expr(), "")
        stmt = stmt.where(ce.ilike(pat, escape="\\"))

    if city and city.strip():
        pat = _ilike_pat(city)
        xe = func.coalesce(_meta_city_expr(), "")
        stmt = stmt.where(xe.ilike(pat, escape="\\"))

    if date_from is not None:
        stmt = stmt.where(ExtractedData.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(ExtractedData.created_at <= date_to)

    return stmt


def _apply_sort(stmt: Select[Any], *, sort: str, keyword: str | None) -> Select[Any]:
    ts = ExtractedData.created_at
    if keyword and keyword.strip():
        pat = _ilike_pat(keyword)
        title_hit = case((func.coalesce(ExtractedData.title, "").ilike(pat, escape="\\"), 1), else_=0)
        text_hit = case((func.coalesce(ExtractedData.text_content, "").ilike(pat, escape="\\"), 1), else_=0)
        rank = title_hit + text_hit
        if sort == "oldest":
            return stmt.order_by(rank.desc(), ts.asc().nulls_last(), ExtractedData.id.asc())
        return stmt.order_by(rank.desc(), ts.desc().nulls_last(), ExtractedData.id.desc())

    if sort == "oldest":
        return stmt.order_by(ts.asc().nulls_last(), ExtractedData.id.asc())
    return stmt.order_by(ts.desc().nulls_last(), ExtractedData.id.desc())


async def search_extracted(
    session: AsyncSession,
    *,
    organization_id: UUID,
    keyword: str | None = None,
    country: str | None = None,
    city: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    job_id: UUID | None = None,
    source_id: UUID | None = None,
    page: int = 1,
    limit: int = 20,
    sort: str = "newest",
) -> SearchResponse:
    limit = max(1, min(100, limit))
    page = max(1, page)
    offset = (page - 1) * limit

    base = _apply_filters(
        _base_select(),
        organization_id=organization_id,
        keyword=keyword,
        country=country,
        city=city,
        date_from=date_from,
        date_to=date_to,
        job_id=job_id,
        source_id=source_id,
    )

    logger.info(
        "search_extracted.query",
        extra={
            "keyword_set": bool((keyword or "").strip()),
            "country_set": bool((country or "").strip()),
            "city_set": bool((city or "").strip()),
            "date_from_set": date_from is not None,
            "date_to_set": date_to is not None,
            "job_id_set": job_id is not None,
            "source_id_set": source_id is not None,
            "page": page,
            "limit": limit,
            "sort": sort,
        },
    )

    count_stmt = select(func.count()).select_from(base.subquery())
    total = int((await session.execute(count_stmt)).scalar_one())
    logger.info("search_extracted.count", extra={"total": total, "page": page, "limit": limit})

    data_stmt = _apply_sort(base, sort=sort, keyword=keyword).offset(offset).limit(limit)
    result = await session.execute(data_stmt)
    rows = result.all()

    items: list[SearchHit] = []
    for row in rows:
        ed: ExtractedData = row[0]
        jid: UUID = row[1]
        sid: UUID | None = row[2]
        co = ed.country
        ci = ed.city
        if not co or not str(co).strip():
            pl = ed.payload if isinstance(ed.payload, dict) else {}
            m = pl.get("metadata") if isinstance(pl.get("metadata"), dict) else {}
            co = m.get("country") if isinstance(m.get("country"), str) else co
        if not ci or not str(ci).strip():
            pl = ed.payload if isinstance(ed.payload, dict) else {}
            m = pl.get("metadata") if isinstance(pl.get("metadata"), dict) else {}
            ci = m.get("city") if isinstance(m.get("city"), str) else ci

        items.append(
            SearchHit(
                id=ed.id,
                run_id=ed.run_id,
                job_id=jid,
                source_id=sid,
                page_url=_page_url(ed),
                title=ed.title,
                preview=_preview(ed.text_content),
                created_at=ed.created_at,
                published_date=ed.published_date,
                country=str(co).strip() if co else None,
                city=str(ci).strip() if ci else None,
            ),
        )

    norm_sort = cast(Literal["newest", "oldest"], sort if sort in ("newest", "oldest") else "newest")
    return SearchResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        sort=norm_sort,
    )
