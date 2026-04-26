"""Heuristic entity extraction from HTML/text + JSON-LD (no ML)."""

from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup

_EMAIL_RE = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.I,
)
# International-style phones: optional +, digits/spaces/parens/dots/hyphens, 8–15 digit core
_PHONE_RE = re.compile(
    r"(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{2,4}[\s.-]?\d{2,4}[\s.-]?\d{2,6}[\s.-]?\d{2,6}\b",
)
_STREET_HINT = re.compile(
    r"\b\d{1,6}\s+[\w\s]{3,60}(?:street|st\.?|avenue|ave\.?|road|rd\.?|drive|dr\.?|lane|ln\.?|boulevard|blvd\.?|way|court|ct\.?)\b",
    re.I,
)
_POSTAL_LINE = re.compile(r"\b[A-Z0-9\s-]{3,12}\s+\d{5}(?:-\d{4})?\b", re.I)


def _dedupe_preserve(seq: list[str], *, max_items: int = 200) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for s in seq:
        k = s.strip()
        if not k or k.lower() in seen:
            continue
        seen.add(k.lower())
        out.append(k)
        if len(out) >= max_items:
            break
    return out


def _emails_from_text(text: str) -> list[str]:
    return _dedupe_preserve([m.group(0) for m in _EMAIL_RE.finditer(text or "")])


def _phones_from_text(text: str) -> list[str]:
    raw = [m.group(0).strip() for m in _PHONE_RE.finditer(text or "")]
    out: list[str] = []
    for p in raw:
        digits = re.sub(r"\D", "", p)
        if len(digits) < 8 or len(digits) > 18:
            continue
        if p not in out:
            out.append(p)
    return _dedupe_preserve(out)


def _names_from_headings(soup: BeautifulSoup) -> list[str]:
    out: list[str] = []
    for tag in ("h1", "h2", "h3"):
        for el in soup.find_all(tag):
            t = el.get_text(separator=" ", strip=True)
            if 3 <= len(t) <= 120 and not _EMAIL_RE.search(t):
                out.append(t)
    return _dedupe_preserve(out, max_items=40)


def _addresses_from_text(text: str) -> list[str]:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    hits: list[str] = []
    for i, ln in enumerate(lines):
        if _STREET_HINT.search(ln) or _POSTAL_LINE.search(ln):
            block = ln
            if i + 1 < len(lines) and len(lines[i + 1]) < 80:
                block = f"{ln}, {lines[i + 1]}"
            hits.append(block[:500])
    return _dedupe_preserve(hits, max_items=30)


def _jsonld_objects(html: str | None) -> list[Any]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    out: list[Any] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            out.extend(data)
        else:
            out.append(data)
    return out


def _entities_from_jsonld(html: str | None) -> tuple[list[str], list[str], dict[str, Any]]:
    """Return (names, addresses_snippets, other) from JSON-LD."""
    names: list[str] = []
    addr_bits: list[str] = []
    other: dict[str, Any] = {}

    def walk(o: Any, depth: int = 0) -> None:
        if depth > 14:
            return
        if isinstance(o, dict):
            t = o.get("@type")
            types = t if isinstance(t, list) else ([t] if t else [])
            type_l = {str(x).lower() for x in types if x}
            if "person" in type_l and isinstance(o.get("name"), str):
                names.append(o["name"])
            if "postaladdress" in type_l or "place" in type_l:
                parts = [
                    o.get("streetAddress"),
                    o.get("addressLocality"),
                    o.get("addressRegion"),
                    o.get("postalCode"),
                    o.get("addressCountry"),
                ]
                line = ", ".join(str(p) for p in parts if p)
                if line:
                    addr_bits.append(line)
            for v in o.values():
                walk(v, depth + 1)
        elif isinstance(o, list):
            for it in o:
                walk(it, depth + 1)

    for root in _jsonld_objects(html):
        walk(root)
    if addr_bits:
        other["jsonld_address_lines"] = addr_bits[:20]
    return names, addr_bits, other


def extract_structured_entities(
    *,
    html: str | None,
    text: str | None,
) -> dict[str, Any]:
    """
    Return ``structured_entities`` shape: emails, phones, names, addresses, other.
    """
    plain = text or ""
    soup = BeautifulSoup(html, "html.parser") if html else None
    j_names, j_addrs, j_other = _entities_from_jsonld(html)

    names = _names_from_headings(soup) if soup else []
    names.extend(j_names)
    names = _dedupe_preserve(names, max_items=50)

    emails = _emails_from_text(plain)
    if html:
        emails = _dedupe_preserve(emails + _emails_from_text(html))

    phones = _phones_from_text(plain)
    if html:
        phones = _dedupe_preserve(phones + _phones_from_text(html))

    addresses = _addresses_from_text(plain)
    addresses = _dedupe_preserve(addresses + j_addrs, max_items=40)

    other: dict[str, Any] = dict(j_other)
    return {
        "emails": emails,
        "phones": phones,
        "names": names,
        "addresses": addresses,
        "other": other,
    }
