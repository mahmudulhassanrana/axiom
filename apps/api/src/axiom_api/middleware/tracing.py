"""Request ID, optional W3C traceparent, access logging, and contextvars for structured logs."""

from __future__ import annotations

import logging
import os
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from axiom_api.core.log_context import reset_request_id, reset_trace_id, set_request_id, set_trace_id

logger = logging.getLogger("axiom_api.access")


def _parse_trace_id_from_traceparent(header: str | None) -> str | None:
    """Extract 32-char hex trace id from W3C ``traceparent`` when valid."""
    if not header or not header.strip():
        return None
    parts = header.strip().split("-")
    if len(parts) < 3:
        return None
    if parts[0] not in {"00", "01"}:
        return None
    tid = parts[1].lower()
    if len(tid) == 32 and all(c in "0123456789abcdef" for c in tid):
        return tid
    return None


def _access_log_disabled() -> bool:
    return os.environ.get("LOG_ACCESS_LOG", "true").strip().lower() in {"0", "false", "no"}


def _skip_access_log(path: str) -> bool:
    if _access_log_disabled():
        return True
    raw = (os.environ.get("LOG_ACCESS_SKIP_PATHS") or "/health").strip()
    skip = {p.strip() for p in raw.split(",") if p.strip()}
    return path in skip


class TracingMiddleware(BaseHTTPMiddleware):
    """
    - ``X-Request-ID`` / ``request.state.request_id`` (or inbound header).
    - ``traceparent`` → ``trace_id`` in logs when valid (W3C Trace Context).
    - Contextvars so any code can correlate logs without ``Request``.
    - Structured ``http_request`` access line (unless path skipped).
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get("x-request-id") or request.headers.get("X-Request-ID")
        rid = incoming.strip() if incoming and incoming.strip() else str(uuid.uuid4())
        request.state.request_id = rid

        trace_hdr = request.headers.get("traceparent") or request.headers.get("Traceparent")
        tid = _parse_trace_id_from_traceparent(trace_hdr)
        request.state.trace_id = tid

        tok_rid = set_request_id(rid)
        tok_tid = set_trace_id(tid)
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            if not _skip_access_log(request.url.path):
                client = request.client.host if request.client else None
                logger.info(
                    "http_request",
                    extra={
                        "event": "http_request",
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                        "client_host": client,
                        "http_version": request.scope.get("http_version"),
                    },
                )
            reset_request_id(tok_rid)
            reset_trace_id(tok_tid)
