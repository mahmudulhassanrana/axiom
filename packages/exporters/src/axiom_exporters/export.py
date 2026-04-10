from __future__ import annotations

import csv
import html
import json
import zipfile
from io import BytesIO, StringIO
from typing import Literal

from axiom_extractors import ExtractedDocument

ExportFormat = Literal["json", "csv", "markdown", "html", "zip"]

_MEDIA = {
    "json": ("application/json; charset=utf-8", "json"),
    "csv": ("text/csv; charset=utf-8", "csv"),
    "markdown": ("text/markdown; charset=utf-8", "md"),
    "html": ("text/html; charset=utf-8", "html"),
    "zip": ("application/zip", "zip"),
}


def media_type_for(fmt: ExportFormat) -> str:
    return _MEDIA[fmt][0]


def file_extension_for(fmt: ExportFormat) -> str:
    return _MEDIA[fmt][1]


def export_bytes(doc: ExtractedDocument, fmt: ExportFormat) -> tuple[bytes, str, str]:
    """
    Return ``(body_utf8, media_type, file_extension)`` for the given document and format.
    """
    if fmt == "zip":
        body = _to_zip(doc)
        mt, ext = _MEDIA["zip"]
        return body, mt, ext
    if fmt == "json":
        raw = json.dumps(doc.model_dump(mode="json"), indent=2, ensure_ascii=False)
        body = raw.encode("utf-8")
    elif fmt == "csv":
        body = _to_csv(doc).encode("utf-8")
    elif fmt == "markdown":
        body = _to_markdown(doc).encode("utf-8")
    else:
        body = _to_html(doc).encode("utf-8")
    mt, ext = _MEDIA[fmt]
    return body, mt, ext


def _to_zip(doc: ExtractedDocument) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "document.json",
            json.dumps(doc.model_dump(mode="json"), indent=2, ensure_ascii=False),
        )
        zf.writestr("document.csv", _to_csv(doc))
        zf.writestr("document.md", _to_markdown(doc))
        zf.writestr("document.html", _to_html(doc))
    return buf.getvalue()


def _to_csv(doc: ExtractedDocument) -> str:
    buf = StringIO()
    d = doc.model_dump(mode="json")
    links_json = json.dumps(d.get("links") or [], ensure_ascii=False)
    meta_json = json.dumps(d.get("metadata") or {}, ensure_ascii=False)
    w = csv.writer(buf)
    w.writerow(
        [
            "url",
            "final_url",
            "title",
            "language",
            "extractor_kind",
            "http_status",
            "fetched_at",
            "text",
            "links_json",
            "metadata_json",
            "has_html",
        ],
    )
    w.writerow(
        [
            d.get("url") or "",
            d.get("final_url") or "",
            d.get("title") or "",
            d.get("language") or "",
            d.get("extractor_kind") or "",
            d.get("http_status") if d.get("http_status") is not None else "",
            d.get("fetched_at") or "",
            d.get("text") or "",
            links_json,
            meta_json,
            "yes" if d.get("html") else "no",
        ],
    )
    return buf.getvalue()


def _to_markdown(doc: ExtractedDocument) -> str:
    title = doc.title or "Extracted document"
    lines = [
        f"# {title}",
        "",
        f"- **URL:** `{doc.url}`",
    ]
    if doc.final_url:
        lines.append(f"- **Final URL:** `{doc.final_url}`")
    if doc.language:
        lines.append(f"- **Language:** {doc.language}")
    lines.extend(
        [
            f"- **Extractor:** `{doc.extractor_kind}`",
            f"- **HTTP status:** {doc.http_status}",
            f"- **Fetched at:** {doc.fetched_at.isoformat()}",
            "",
            "## Text",
            "",
            doc.text.strip() or "_(empty)_",
            "",
        ],
    )
    if doc.links:
        lines.extend(["## Links", ""])
        for link in doc.links:
            label = link.text or link.href
            lines.append(f"- [{label}]({link.href})")
        lines.append("")
    if doc.metadata:
        lines.extend(["## Metadata", "", "```json", json.dumps(doc.metadata, indent=2, ensure_ascii=False), "```", ""])
    if doc.html:
        lines.extend(["## Raw HTML", "", "_(omitted in markdown; use HTML export for full HTML)_", ""])
    return "\n".join(lines)


def _to_html(doc: ExtractedDocument) -> str:
    title = html.escape(doc.title or "Extracted document")
    safe_text = html.escape(doc.text)
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{title}</title>",
        "<style>body{font-family:system-ui,sans-serif;max-width:48rem;margin:2rem auto;line-height:1.5;color:#111}pre{white-space:pre-wrap;word-break:break-word;background:#f6f6f6;padding:1rem;border-radius:8px}dl{display:grid;grid-template-columns:auto 1fr;gap:0.25rem 1rem}dt{font-weight:600;color:#444}</style>",
        "</head>",
        "<body>",
        "<article>",
        f"<h1>{title}</h1>",
        "<dl>",
        f"<dt>URL</dt><dd>{html.escape(doc.url)}</dd>",
    ]
    if doc.final_url:
        parts.append(f"<dt>Final URL</dt><dd>{html.escape(doc.final_url)}</dd>")
    if doc.language:
        parts.append(f"<dt>Language</dt><dd>{html.escape(doc.language)}</dd>")
    parts.extend(
        [
            f"<dt>Extractor</dt><dd>{html.escape(doc.extractor_kind)}</dd>",
            f"<dt>HTTP status</dt><dd>{doc.http_status if doc.http_status is not None else ''}</dd>",
            f"<dt>Fetched at</dt><dd>{html.escape(doc.fetched_at.isoformat())}</dd>",
            "</dl>",
            "<h2>Text</h2>",
            f"<pre>{safe_text}</pre>",
        ],
    )
    if doc.links:
        parts.extend(["<h2>Links</h2>", "<ul>"])
        for link in doc.links:
            label = html.escape(link.text or link.href)
            parts.append(f'<li><a href="{html.escape(link.href, quote=True)}">{label}</a></li>')
        parts.append("</ul>")
    if doc.metadata:
        parts.extend(
            [
                "<h2>Metadata</h2>",
                "<pre>",
                html.escape(json.dumps(doc.metadata, indent=2, ensure_ascii=False)),
                "</pre>",
            ],
        )
    if doc.html:
        parts.extend(["<h2>Raw HTML</h2>", "<pre>", html.escape(doc.html[:500_000]), "</pre>"])
    parts.extend(["</article>", "</body>", "</html>"])
    return "\n".join(parts)
