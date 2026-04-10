"""Reject oversized request bodies using ``Content-Length`` (fast path for JSON APIs)."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.status import HTTP_413_REQUEST_ENTITY_TOO_LARGE
from starlette.types import ASGIApp

from axiom_api.core.deployment_security import max_request_body_bytes
from axiom_api.core.error_envelope import error_body
class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """If ``Content-Length`` exceeds the configured maximum, return 413 without reading the body."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in {"POST", "PUT", "PATCH"}:
            cl = request.headers.get("content-length")
            if cl is not None and cl.isdigit():
                n = int(cl)
                limit = max_request_body_bytes()
                if n > limit:
                    rid = getattr(request.state, "request_id", None)
                    return JSONResponse(
                        status_code=HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content=error_body(
                            code="payload_too_large",
                            message=f"Request body exceeds maximum of {limit} bytes",
                            request_id=rid,
                        ),
                    )
        return await call_next(request)
