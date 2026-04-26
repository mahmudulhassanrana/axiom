"""Aggregate job extraction rows into downloadable bundles (JSON, CSV, PDF)."""

from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Any

from axiom_api.db.models.extracted_data import ExtractedData
from axiom_api.db.models.job import Job


def _meta(pl: dict[str, Any]) -> dict[str, Any]:
    m = pl.get("metadata")
    return m if isinstance(m, dict) else {}


def job_results_json_bytes(job: Job, rows: list[ExtractedData]) -> tuple[bytes, str, str]:
    payload: list[dict[str, Any]] = []
    for r in rows:
        pl = dict(r.payload) if isinstance(r.payload, dict) else {}
        meta = _meta(pl)
        payload.append(
            {
                "id": str(r.id),
                "run_id": str(r.run_id),
                "page_url": pl.get("page_url") or r.source_url,
                "source_url": r.source_url,
                "final_url": r.final_url,
                "title": r.title,
                "text_content": r.text_content,
                "full_text": meta.get("full_text") or r.text_content,
                "headings": meta.get("headings"),
                "internal_links": meta.get("internal_links"),
                "external_links": meta.get("external_links"),
                "crawl_source": meta.get("crawl_source"),
                "content_quality_score": meta.get("content_quality_score"),
                "extractor_kind": r.extractor_kind,
                "http_status": r.http_status,
                "links": pl.get("links") or [],
                "images": pl.get("images") or [],
                "files": pl.get("files") or [],
                "file_links": pl.get("file_links") or pl.get("files") or [],
                "structured_entities": pl.get("structured_entities")
                if isinstance(pl.get("structured_entities"), dict)
                else {},
                "extraction_type": getattr(r, "extraction_type", None)
                or (meta.get("extraction_type") if isinstance(meta.get("extraction_type"), str) else None)
                or (pl.get("extraction_type") if isinstance(pl.get("extraction_type"), str) else None),
                "metadata": meta,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            },
        )
    body = json.dumps(
        {"job_id": str(job.id), "url": job.url, "status": job.status, "results": payload},
        indent=2,
        ensure_ascii=False,
    ).encode("utf-8")
    return body, "application/json; charset=utf-8", "json"


def job_results_csv_bytes(job: Job, rows: list[ExtractedData]) -> tuple[bytes, str, str]:
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "job_id",
            "extracted_id",
            "run_id",
            "page_url",
            "title",
            "text_preview",
            "link_count",
            "image_count",
            "file_count",
            "emails",
            "phones",
            "names",
            "addresses",
            "extraction_type",
            "http_status",
        ],
    )
    for r in rows:
        pl = dict(r.payload) if isinstance(r.payload, dict) else {}
        page_url = pl.get("page_url") or r.source_url
        links = pl.get("links") or []
        imgs = pl.get("images") or []
        files = pl.get("files") or []
        se = pl.get("structured_entities") if isinstance(pl.get("structured_entities"), dict) else {}
        em = ";".join(str(x) for x in (se.get("emails") or [])[:50])
        ph = ";".join(str(x) for x in (se.get("phones") or [])[:50])
        nm = ";".join(str(x) for x in (se.get("names") or [])[:30])
        ad = ";".join(str(x) for x in (se.get("addresses") or [])[:20])
        ext_t = getattr(r, "extraction_type", None) or (
            pl.get("extraction_type") if isinstance(pl.get("extraction_type"), str) else ""
        )
        text = (r.text_content or "")[:2000]
        w.writerow(
            [
                str(job.id),
                str(r.id),
                str(r.run_id),
                page_url,
                r.title or "",
                text,
                len(links) if isinstance(links, list) else 0,
                len(imgs) if isinstance(imgs, list) else 0,
                len(files) if isinstance(files, list) else 0,
                em,
                ph,
                nm,
                ad,
                ext_t or "",
                r.http_status if r.http_status is not None else "",
            ],
        )
    return buf.getvalue().encode("utf-8"), "text/csv; charset=utf-8", "csv"


def _try_register_dejavu(pdf: Any) -> bool:
    try:
        import fpdf
        from pathlib import Path

        root = Path(fpdf.__file__).resolve().parent
        font_dir = root / "font"
        candidates = [
            (font_dir / "DejaVuSans.ttf", font_dir / "DejaVuSans-Bold.ttf"),
            (font_dir / "unifont" / "DejaVuSans.ttf", font_dir / "unifont" / "DejaVuSans-Bold.ttf"),
        ]
        for reg, bold in candidates:
            if reg.is_file():
                try:
                    pdf.add_font("DejaVu", style="", fname=str(reg))
                    if bold.is_file():
                        pdf.add_font("DejaVu", style="B", fname=str(bold))
                    else:
                        pdf.add_font("DejaVu", style="B", fname=str(reg))
                except Exception:
                    return False
                return True
    except Exception:
        return False
    return False


def _ascii_fallback(s: str, *, max_len: int) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    if len(s) > max_len:
        s = s[: max_len - 3] + "..."
    out: list[str] = []
    for ch in s:
        o = ord(ch)
        if ch == "\n":
            out.append("\n")
        elif 32 <= o <= 126 or ch in "\n\t":
            out.append(ch)
        elif o in (0x2013, 0x2014):
            out.append("-")
        else:
            out.append("?")
    return "".join(out)


def _ensure_vertical_room(pdf: Any, needed_mm: float) -> None:
    if pdf.get_y() + needed_mm > pdf.h - pdf.b_margin:
        pdf.add_page()


def _content_width_mm(pdf: Any) -> float:
    """Usable inner width; never zero (fpdf2 raises if multi_cell width < one glyph)."""
    try:
        epw = getattr(pdf, "epw", None)
        if epw is not None:
            return max(30.0, float(epw))
    except Exception:
        pass
    return max(30.0, float(pdf.w) - float(pdf.l_margin) - float(pdf.r_margin))


def _safe_multi_cell(pdf: Any, line_height: float, text: str, *, use_unicode: bool) -> None:
    """Reset X to left margin and use explicit width — avoids 'Not enough horizontal space' after page breaks."""
    w = _content_width_mm(pdf)
    lh = max(line_height, 3.5)
    raw = text if text is not None else ""
    raw = raw.replace("\x00", " ").strip()
    if not raw:
        raw = " "
    if not use_unicode:
        raw = _ascii_fallback(raw, max_len=50000)
    pdf.set_x(float(pdf.l_margin))
    pdf.multi_cell(w, lh, raw)


def _write_section_title(pdf: Any, title: str, *, use_unicode: bool, lh: float) -> None:
    _ensure_vertical_room(pdf, lh * 3)
    fam = "DejaVu" if use_unicode else "Helvetica"
    pdf.set_font(fam, "B", 11)
    _safe_multi_cell(pdf, lh, title, use_unicode=use_unicode)
    pdf.set_font(fam, "", 9)


def _write_body(pdf: Any, text: str, *, use_unicode: bool, lh: float, max_chars: int) -> None:
    fam = "DejaVu" if use_unicode else "Helvetica"
    pdf.set_font(fam, "", 9)
    body = text if len(text) <= max_chars else text[: max_chars - 20] + "\n… [truncated]"
    row_h = max(lh, 4.0)
    for para in body.split("\n"):
        line = para.strip() or " "
        _ensure_vertical_room(pdf, row_h * 2)
        _safe_multi_cell(pdf, row_h, line, use_unicode=use_unicode)


def job_results_pdf_bytes(job: Job, rows: list[ExtractedData]) -> tuple[bytes, str, str]:
    try:
        from fpdf import FPDF
    except ImportError as exc:
        raise RuntimeError("fpdf2 is required for PDF export") from exc

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)
    use_unicode = _try_register_dejavu(pdf)
    pdf.add_page()
    lh = 5.0
    fam = "DejaVu" if use_unicode else "Helvetica"
    pdf.set_font(fam, "B", 14)
    header = f"Axiom job export\n{job.url or ''}\nID: {job.id}\nStatus: {job.status}"
    if not use_unicode:
        header = _ascii_fallback(header, max_len=2000)
    for hdr_line in header.split("\n"):
        _safe_multi_cell(pdf, 8.0, hdr_line, use_unicode=use_unicode)
    pdf.ln(4)

    for i, r in enumerate(rows, start=1):
        pl = dict(r.payload) if isinstance(r.payload, dict) else {}
        meta = _meta(pl)
        page_url = str(pl.get("page_url") or r.source_url or "")
        title = str(r.title or "(no title)")
        full_text = str(meta.get("full_text") or r.text_content or "")
        links = pl.get("links") if isinstance(pl.get("links"), list) else []
        imgs = pl.get("images") if isinstance(pl.get("images"), list) else []
        files = pl.get("files") if isinstance(pl.get("files"), list) else []
        headings = meta.get("headings")
        crawl_source = meta.get("crawl_source")
        quality = meta.get("content_quality_score")

        _write_section_title(pdf, f"{i}. {title[:300]}", use_unicode=use_unicode, lh=lh)

        pdf.set_font(fam, "", 9)
        meta_lines = [
            f"URL: {page_url}",
            f"HTTP: {r.http_status!s}  Extractor: {r.extractor_kind}",
            f"Images: {len(imgs)}  Files: {len(files)}  Links: {len(links)}",
        ]
        if crawl_source is not None:
            meta_lines.append(f"Crawl source: {crawl_source}")
        if quality is not None:
            meta_lines.append(f"Content quality: {quality}")
        se = pl.get("structured_entities") if isinstance(pl.get("structured_entities"), dict) else {}
        ext_type = getattr(r, "extraction_type", None) or pl.get("extraction_type")
        if ext_type:
            meta_lines.append(f"Extraction type: {ext_type}")
        for ml in meta_lines:
            if not use_unicode:
                ml = _ascii_fallback(ml, max_len=4000)
            _ensure_vertical_room(pdf, lh * 2)
            _safe_multi_cell(pdf, lh, ml, use_unicode=use_unicode)

        if isinstance(headings, list) and headings:
            _write_section_title(pdf, "Headings", use_unicode=use_unicode, lh=lh)
            cap = 0
            for h in headings[:40]:
                if not isinstance(h, dict):
                    continue
                lv = h.get("level", "")
                ht = str(h.get("text", ""))[:500]
                if not ht:
                    continue
                line = f"H{lv}: {ht}"
                if not use_unicode:
                    line = _ascii_fallback(line, max_len=600)
                _ensure_vertical_room(pdf, lh * 2)
                pdf.set_font(fam, "", 9)
                _safe_multi_cell(pdf, lh, line, use_unicode=use_unicode)
                cap += 1
                if cap >= 40:
                    break

        if isinstance(meta, dict) and meta.get("meta_tags"):
            tags = meta["meta_tags"]
            if isinstance(tags, dict) and tags:
                _write_section_title(pdf, "Meta tags (sample)", use_unicode=use_unicode, lh=lh)
                pdf.set_font(fam, "", 8)
                row_h = max(4.0, lh - 0.5)
                for k, v in list(tags.items())[:25]:
                    line = f"{k}: {str(v)[:400]}"
                    if not use_unicode:
                        line = _ascii_fallback(line, max_len=500)
                    _ensure_vertical_room(pdf, row_h * 2)
                    _safe_multi_cell(pdf, row_h, line, use_unicode=use_unicode)

        if se:
            _write_section_title(pdf, "Detected entities (sample)", use_unicode=use_unicode, lh=lh)
            pdf.set_font(fam, "", 8)
            eh = max(4.0, lh - 0.5)
            for label, key in (
                ("Emails", "emails"),
                ("Phones", "phones"),
                ("Names", "names"),
                ("Addresses", "addresses"),
            ):
                vals = se.get(key) if isinstance(se.get(key), list) else []
                if not vals:
                    continue
                line = f"{label}: " + "; ".join(str(v)[:120] for v in vals[:12])
                if not use_unicode:
                    line = _ascii_fallback(line, max_len=2000)
                _ensure_vertical_room(pdf, eh * 2)
                _safe_multi_cell(pdf, eh, line, use_unicode=use_unicode)

        _write_section_title(pdf, "Links (first 60)", use_unicode=use_unicode, lh=lh)
        pdf.set_font(fam, "", 8)
        link_h = max(4.0, lh - 0.5)
        for j, link in enumerate(links[:60]):
            if isinstance(link, dict):
                href = str(link.get("href", ""))[:800]
                lt = str(link.get("text") or "")[:200]
                line = f"{j + 1}. {href}" + (f" — {lt}" if lt else "")
            else:
                line = str(link)[:900]
            if not use_unicode:
                line = _ascii_fallback(line, max_len=1200)
            _ensure_vertical_room(pdf, link_h * 2)
            _safe_multi_cell(pdf, link_h, line, use_unicode=use_unicode)

        _write_section_title(pdf, "Text content", use_unicode=use_unicode, lh=lh)
        _write_body(pdf, full_text, use_unicode=use_unicode, lh=lh, max_chars=12000)
        pdf.ln(3)

    raw = pdf.output(dest="S")
    if isinstance(raw, str):
        body = raw.encode("latin-1", errors="replace")
    elif isinstance(raw, bytearray):
        body = bytes(raw)
    else:
        body = raw if isinstance(raw, bytes) else bytes(raw)
    return body, "application/pdf", "pdf"
