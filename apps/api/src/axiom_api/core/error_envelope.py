from __future__ import annotations

from typing import Any
from uuid import UUID

from starlette.requests import Request

from axiom_api.core.log_context import get_request_id
from axiom_api.types.errors import ErrorDetailBody, ErrorEnvelope


def request_id_from_request(request: Request) -> str | None:
    rid = getattr(request.state, "request_id", None)
    if rid is not None:
        return str(rid)
    return get_request_id()


def status_to_error_code(status_code: int) -> str:
    return _STATUS_CODES.get(status_code, "http_error")


_STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    413: "payload_too_large",
    422: "validation_error",
    429: "too_many_requests",
    502: "bad_gateway",
    503: "service_unavailable",
}


def error_body(
    *,
    code: str,
    message: str,
    request_id: str | UUID | None,
    fields: list[dict[str, Any]] | None = None,
) -> ErrorEnvelope:
    err: ErrorDetailBody = {
        "code": code,
        "message": message,
        "request_id": str(request_id) if request_id is not None else None,
    }
    if fields is not None:
        err["fields"] = fields
    return {"error": err}


def merge_request_id(detail: ErrorDetailBody, request_id: str | UUID | None) -> ErrorEnvelope:
    out: ErrorDetailBody = {**detail}
    out.setdefault("request_id", str(request_id) if request_id is not None else None)
    return {"error": out}
