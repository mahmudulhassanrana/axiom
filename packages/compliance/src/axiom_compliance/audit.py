from __future__ import annotations

import logging
from typing import Any

_audit_logger = logging.getLogger("axiom.compliance.audit")


def log_scrape_audit(event: str, **fields: Any) -> None:
    """Structured audit line for log aggregation (set `extra` for JSON loggers)."""
    payload = {"axiom_audit": True, "axiom_event": event, **fields}
    _audit_logger.info(event, extra=payload)
