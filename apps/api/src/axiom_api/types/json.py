"""JSON-compatible value type for JSONB columns and API payloads."""

from __future__ import annotations

from typing_extensions import TypeAliasType

# Named recursive alias so Pydantic/mypy resolve JSONValue and JSON Schema can emit $defs.
# (PEP 695: use `type JSONValue = str | ... | list[JSONValue] | ...` on Python 3.12+.)
JSONValue = TypeAliasType(
    "JSONValue",
    "str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]",
)
