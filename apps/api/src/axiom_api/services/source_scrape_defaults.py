"""Map :class:`Source` rows to scrape job payload / Celery kwargs (single place of truth)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from axiom_api.db.models.source import Source


def crawl_max_pages_from_source(source: Source) -> int:
    if source.crawl_type == "single_page":
        return 1
    if source.crawl_type == "sitemap":
        return max(1, min(50, int(source.max_pages)))
    return max(1, min(50, int(source.max_pages)))


def delay_pair_from_source(source: Source) -> tuple[float, float]:
    dmin = float(source.delay_min)
    dmax = float(source.delay_max)
    if dmax < dmin:
        dmin, dmax = dmax, dmin
    mid = (dmin + dmax) / 2.0
    jitter = max(0.0, (dmax - dmin) / 2.0)
    return mid, jitter


def payload_from_source(source: Source) -> dict[str, Any]:
    delay_s, jitter_s = delay_pair_from_source(source)
    return {
        "url": str(source.base_url).strip(),
        "engine": str(source.scrape_engine),
        "include_html": bool(source.include_html),
        "crawl_type": str(source.crawl_type),
        "crawl_max_pages": crawl_max_pages_from_source(source),
        "crawl_delay_seconds": delay_s,
        "crawl_jitter_seconds": jitter_s,
        "crawl_allow_external": bool(source.allow_external),
        "crawl_max_external_pages": 25,
        "crawl_max_external_per_host": 5,
        "pre_fetch_jitter_max_seconds": 0.0,
        "sitemap_url": source.sitemap_url,
    }
