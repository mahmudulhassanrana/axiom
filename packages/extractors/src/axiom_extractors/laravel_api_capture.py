"""Detect Laravel-style paginated JSON (data + meta.links) and normalize list rows."""

from __future__ import annotations

import logging
import os
import random
import re
import time
from typing import Any
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)


def is_laravel_paginated_json(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    data = obj.get("data")
    meta = obj.get("meta")
    if not isinstance(data, list) or not isinstance(meta, dict):
        return False
    if len(data) < 1:
        return False
    need = ("current_page", "last_page", "per_page", "total")
    return all(k in meta for k in need)


def _max_api_pages() -> int:
    raw = (os.environ.get("AXIOM_MEMBER_API_MAX_PAGES") or "20").strip()
    try:
        n = int(raw, 10)
    except ValueError:
        n = 20
    return max(1, min(200, n))


def normalize_member_row(obj: dict[str, Any], *, source_url: str) -> dict[str, Any]:
    """Map varied API keys to a stable public shape."""
    name = (
        obj.get("representative_name")
        or obj.get("rep_name")
        or obj.get("name")
        or obj.get("Rep_Name")
        or obj.get("rep_name_en")
    )
    company = obj.get("company_name") or obj.get("company") or obj.get("organization")
    addr = obj.get("address") or obj.get("office_address") or obj.get("location")
    phone = obj.get("phone") or obj.get("mobile") or obj.get("telephone") or obj.get("contact_number")
    email = obj.get("email") or obj.get("contact_email")
    website = obj.get("website") or obj.get("web") or obj.get("FullUrl")
    designation = (
        obj.get("designation")
        or obj.get("title")
        or obj.get("role")
        or obj.get("position")
    )
    return {
        "name": str(name).strip() if name else None,
        "company": str(company).strip() if company else None,
        "designation": str(designation).strip() if designation else None,
        "address": str(addr).strip() if addr else None,
        "phone": str(phone).strip() if phone else None,
        "email": str(email).strip() if email else None,
        "website": str(website).strip() if website else None,
        "membership_id": str(obj.get("membership_id") or "").strip() or None,
        "membership_type": str(obj.get("membership_type") or "").strip() or None,
        "source_url": source_url,
        "detail_page_url": source_url,
        "raw": {k: v for k, v in obj.items() if k in ("short_profile", "establishment_year", "establishment_month", "membership_no")},
    }


def _same_origin(a: str, b: str) -> bool:
    try:
        pa, pb = urlparse(a), urlparse(b)
        return (pa.netloc or "").lower() == (pb.netloc or "").lower()
    except Exception:
        return False


def _template_paginated_url(first_url: str, page: int) -> str:
    """Replace page= query in Laravel paginator URLs."""
    parsed = urlparse(first_url)
    q = parsed.query
    if re.search(r"(^|[&?])page=", q):
        nq = re.sub(r"(^|[?&])page=[^&]*", lambda m: f"{m.group(1)}page={page}", q, count=1)
    else:
        sep = "&" if q else ""
        nq = f"{q}{sep}page={page}" if q else f"page={page}"
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, nq, ""))


def collect_extra_laravel_pages(
    *,
    request_get: Any,
    first_url: str,
    meta: dict[str, Any],
    seed_url: str,
    referer: str,
    first_body: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """GET additional pages via Playwright APIRequestContext.get (same cookies)."""
    try:
        last = int(meta.get("last_page") or 1)
    except (TypeError, ValueError):
        last = 1
    cap = min(last, _max_api_pages())
    if cap <= 1:
        return []
    headers = {"Accept": "application/json", "Referer": referer}
    merged: list[dict[str, Any]] = []
    fetched_urls: set[str] = set()

    root = first_body if isinstance(first_body, dict) else {}
    links_block = root.get("links") if isinstance(root.get("links"), dict) else {}
    raw_next = links_block.get("next")
    next_url: str | None = None
    if isinstance(raw_next, str) and raw_next.strip():
        next_url = raw_next.strip()
    if next_url and next_url.lower() in ("null", "none", "#"):
        next_url = None

    seen_chain: set[str] = set()
    page_idx = int(meta.get("current_page") or 1)

    while next_url and page_idx < cap:
        if next_url in seen_chain:
            logger.warning("laravel_api.pagination_cycle", extra={"url": next_url})
            break
        seen_chain.add(next_url)
        if not _same_origin(next_url, seed_url):
            break
        time.sleep(random.uniform(0.9, 2.8))
        try:
            resp = request_get.get(next_url, headers=headers, timeout=30_000)
            if not resp.ok:
                logger.warning(
                    "laravel_api.page_http",
                    extra={"url": next_url, "status": resp.status},
                )
                break
            body = resp.json()
        except Exception as exc:
            logger.warning("laravel_api.page_error", extra={"url": next_url, "error": str(exc)})
            break
        if not isinstance(body, dict):
            break
        rows = body.get("data")
        if not isinstance(rows, list) or len(rows) == 0:
            logger.info("laravel_api.pagination_empty", extra={"url": next_url})
            break
        page_idx += 1
        fetched_urls.add(next_url)
        for item in rows:
            if isinstance(item, dict):
                merged.append(normalize_member_row(item, source_url=next_url))
        logger.info(
            "laravel_api.pagination_page",
            extra={"page": page_idx, "rows": len(rows), "url": next_url},
        )
        lb = body.get("links") if isinstance(body.get("links"), dict) else {}
        nu = lb.get("next")
        next_url = nu.strip() if isinstance(nu, str) and nu.strip() else None
        if next_url and next_url.lower() in ("null", "none", "#"):
            next_url = None

    for page in range(2, cap + 1):
        u = _template_paginated_url(first_url, page)
        if not _same_origin(u, seed_url):
            break
        if u in fetched_urls:
            continue
        time.sleep(random.uniform(0.9, 2.8))
        try:
            resp = request_get.get(u, headers=headers, timeout=30_000)
            if not resp.ok:
                logger.warning("laravel_api.page_http", extra={"url": u, "status": resp.status})
                continue
            body = resp.json()
        except Exception as exc:
            logger.warning("laravel_api.page_error", extra={"url": u, "error": str(exc)})
            continue
        if not isinstance(body, dict):
            continue
        rows = body.get("data")
        if not isinstance(rows, list) or len(rows) == 0:
            continue
        fetched_urls.add(u)
        for item in rows:
            if isinstance(item, dict):
                merged.append(normalize_member_row(item, source_url=u))
        logger.info(
            "laravel_api.pagination_page",
            extra={"page": page, "rows": len(rows), "url": u},
        )
    return merged


def pick_best_laravel_payload(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_len = -1
    for c in candidates:
        body = c.get("json")
        if not is_laravel_paginated_json(body):
            continue
        ln = len(body.get("data") or [])
        if ln > best_len:
            best_len = ln
            best = c
    return best


def records_text_block(records: list[dict[str, Any]], *, max_lines: int = 500) -> str:
    lines: list[str] = []
    for r in records[:max_lines]:
        parts = [
            r.get("company") or "",
            r.get("name") or "",
            r.get("membership_id") or "",
            r.get("membership_type") or "",
            r.get("phone") or "",
            r.get("email") or "",
            r.get("website") or "",
        ]
        line = " | ".join(p for p in parts if p)
        raw = r.get("raw") if isinstance(r.get("raw"), dict) else {}
        sp = raw.get("short_profile") if isinstance(raw, dict) else None
        if isinstance(sp, str) and sp.strip():
            line += f" — {sp.strip()[:400]}"
        if line.strip():
            lines.append(line.strip())
    return "\n".join(lines)
