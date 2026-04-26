"""Merge :class:`JobCreateRequest` with optional :class:`Source` defaults."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from axiom_api.schemas.jobs import JobCreateRequest
from axiom_api.services.source_scrape_defaults import payload_from_source

if TYPE_CHECKING:
    from axiom_api.db.models.source import Source


def build_merged_job_payload(body: JobCreateRequest, source: Source | None) -> dict[str, Any]:
    fs = body.model_fields_set
    sp: dict[str, Any] = payload_from_source(source) if source else {}

    url_str = str(body.url).strip() if body.url is not None else str(sp.get("url", "")).strip()
    if not url_str:
        msg = "Could not resolve target URL (provide url or source with base_url)."
        raise ValueError(msg)

    out: dict[str, Any] = {
        "url": url_str,
        "engine": body.engine if "engine" in fs else sp.get("engine", body.engine),
        "include_html": body.include_html if "include_html" in fs else sp.get("include_html", body.include_html),
        "crawl_max_pages": body.crawl_max_pages
        if "crawl_max_pages" in fs
        else sp.get("crawl_max_pages", body.crawl_max_pages),
        "crawl_delay_seconds": body.crawl_delay_seconds
        if "crawl_delay_seconds" in fs
        else sp.get("crawl_delay_seconds", body.crawl_delay_seconds),
        "crawl_jitter_seconds": body.crawl_jitter_seconds
        if "crawl_jitter_seconds" in fs
        else sp.get("crawl_jitter_seconds", body.crawl_jitter_seconds),
        "crawl_allow_external": body.crawl_allow_external
        if "crawl_allow_external" in fs
        else sp.get("crawl_allow_external", body.crawl_allow_external),
        "crawl_max_external_pages": body.crawl_max_external_pages
        if "crawl_max_external_pages" in fs
        else sp.get("crawl_max_external_pages", body.crawl_max_external_pages),
        "crawl_max_external_per_host": body.crawl_max_external_per_host
        if "crawl_max_external_per_host" in fs
        else sp.get("crawl_max_external_per_host", body.crawl_max_external_per_host),
        "pre_fetch_jitter_max_seconds": body.pre_fetch_jitter_max_seconds
        if "pre_fetch_jitter_max_seconds" in fs
        else sp.get("pre_fetch_jitter_max_seconds", body.pre_fetch_jitter_max_seconds),
        "robots_override": bool(body.robots_override) if "robots_override" in fs else False,
    }

    if source:
        out["crawl_type"] = str(sp.get("crawl_type", "single_page"))
        if "crawl_type" in fs and body.crawl_type is not None:
            out["crawl_type"] = str(body.crawl_type)
        su = sp.get("sitemap_url")
        out["sitemap_url"] = str(su).strip() if su else None
        if "sitemap_url" in fs and body.sitemap_url is not None:
            out["sitemap_url"] = str(body.sitemap_url).strip()
    else:
        if "crawl_type" in fs and body.crawl_type is not None:
            out["crawl_type"] = str(body.crawl_type)
        else:
            out["crawl_type"] = "single_page" if int(out["crawl_max_pages"]) <= 1 else "multi_page"
        out["sitemap_url"] = str(body.sitemap_url).strip() if body.sitemap_url else None

    if str(out.get("crawl_type", "")).strip().lower() == "multi_page":
        out["crawl_max_pages"] = max(2, int(out["crawl_max_pages"]))

    return out
