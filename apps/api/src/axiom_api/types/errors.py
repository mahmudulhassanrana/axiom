"""Typed shapes for HTTP error JSON bodies."""

from __future__ import annotations

from typing import Any, Required, TypedDict


class ErrorDetailBody(TypedDict, total=False):
    """``error`` object returned by the global exception handlers."""

    code: Required[str]
    message: Required[str]
    request_id: str | None
    fields: list[dict[str, Any]]


class ErrorEnvelope(TypedDict):
    error: ErrorDetailBody
