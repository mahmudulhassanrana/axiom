from __future__ import annotations

import logging
import traceback
from typing import cast

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

from axiom_api.core.env import is_production
from axiom_api.core.error_envelope import (
    error_body,
    merge_request_id,
    request_id_from_request,
    status_to_error_code,
)
from axiom_api.core.log_context import get_trace_id
from axiom_api.types.errors import ErrorDetailBody, ErrorEnvelope

logger = logging.getLogger("axiom_api.errors")


def _http_exception_detail_to_envelope(
    exc: HTTPException,
    request: Request,
) -> ErrorEnvelope:
    rid = request_id_from_request(request)
    detail = exc.detail

    if isinstance(detail, dict):
        if "code" in detail and "message" in detail:
            return merge_request_id(cast(ErrorDetailBody, detail), rid)
        message = detail.get("message", jsonable_encoder(detail))
        code = str(detail.get("code", status_to_error_code(exc.status_code)))
        return error_body(
            code=code,
            message=message if isinstance(message, str) else str(message),
            request_id=rid,
        )

    if isinstance(detail, str):
        return error_body(
            code=status_to_error_code(exc.status_code),
            message=detail,
            request_id=rid,
        )

    return error_body(
        code=status_to_error_code(exc.status_code),
        message=jsonable_encoder(detail),
        request_id=rid,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    body = _http_exception_detail_to_envelope(exc, request)
    headers = {k: v for k, v in (exc.headers or {}).items()}
    return JSONResponse(status_code=exc.status_code, content=body, headers=headers)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    rid = request_id_from_request(request)
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_body(
            code="validation_error",
            message="Request validation failed",
            request_id=rid,
            fields=jsonable_encoder(exc.errors()),
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    rid = request_id_from_request(request)
    logger.exception(
        "unhandled_exception",
        extra={
            "event": "unhandled_exception",
            "request_id": rid,
            "trace_id": get_trace_id(),
            "path": request.url.path,
        },
    )
    if is_production():
        message = "An unexpected error occurred. Please try again later."
    else:
        message = f"{type(exc).__name__}: {exc}"
        logger.debug("exception_traceback", extra={"tb": traceback.format_exc()})
    return JSONResponse(
        status_code=500,
        content=error_body(code="internal_error", message=message, request_id=rid),
    )


def register_exception_handlers(app) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
