"""Structured logging (JSON or text) with request/trace context on every record."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any

from axiom_api import __version__
from axiom_api.core.log_context import get_request_id, get_trace_id

_configured = False


class RequestContextFilter(logging.Filter):
    """Attach request_id and trace_id from contextvars for formatters."""

    def filter(self, record: logging.LogRecord) -> bool:
        rid = get_request_id()
        tid = get_trace_id()
        record.request_id = rid if rid else "-"
        record.trace_id = tid if tid else "-"
        return True


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line (common for log aggregators)."""

    _EXTRA_KEYS = frozenset(
        {
            "event",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "app_version",
            "http_version",
            "client_host",
        },
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        rid = getattr(record, "request_id", None)
        if rid and rid != "-":
            payload["request_id"] = rid
        tid = getattr(record, "trace_id", None)
        if tid and tid != "-":
            payload["trace_id"] = tid
        for key in self._EXTRA_KEYS:
            if hasattr(record, key):
                val = getattr(record, key)
                if val is not None:
                    payload[key] = val
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info).strip()
        return json.dumps(payload, default=str)


def configure_logging(*, force: bool = False) -> None:
    """Configure the ``axiom_api`` logger tree (idempotent unless ``force``)."""
    global _configured
    if _configured and not force:
        return

    level_name = (os.environ.get("LOG_LEVEL") or "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt = (os.environ.get("LOG_FORMAT") or "text").strip().lower()

    log = logging.getLogger("axiom_api")
    log.handlers.clear()
    log.setLevel(level)
    log.propagate = False

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.addFilter(RequestContextFilter())
    if fmt == "json":
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s "
                "[request_id=%(request_id)s trace_id=%(trace_id)s] %(message)s",
            ),
        )
    log.addHandler(handler)

    _configured = True


def log_service_start() -> None:
    logging.getLogger("axiom_api").info(
        "axiom api starting",
        extra={"event": "service_start", "app_version": __version__},
    )


def log_service_stop() -> None:
    logging.getLogger("axiom_api").info("axiom api stopping", extra={"event": "service_stop"})
