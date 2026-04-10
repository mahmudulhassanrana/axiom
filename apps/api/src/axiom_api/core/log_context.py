"""Request-scoped identifiers for logs (async-safe via contextvars)."""

from __future__ import annotations

from contextvars import ContextVar, Token

_request_id: ContextVar[str | None] = ContextVar("axiom_request_id", default=None)
_trace_id: ContextVar[str | None] = ContextVar("axiom_trace_id", default=None)


def get_request_id() -> str | None:
    return _request_id.get()


def get_trace_id() -> str | None:
    return _trace_id.get()


def set_request_id(value: str | None) -> Token:
    return _request_id.set(value)


def set_trace_id(value: str | None) -> Token:
    return _trace_id.set(value)


def reset_request_id(token: Token) -> None:
    _request_id.reset(token)


def reset_trace_id(token: Token) -> None:
    _trace_id.reset(token)
