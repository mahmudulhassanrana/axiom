from __future__ import annotations

from axiom_api.core.env import is_production


def client_safe_detail(
    *,
    code: str,
    production_message: str,
    developer_message: str | None = None,
) -> dict[str, str]:
    """Build structured HTTPException detail: safe text in production, richer in development."""
    if is_production():
        return {"code": code, "message": production_message}
    return {
        "code": code,
        "message": developer_message if developer_message is not None else production_message,
    }


def format_upstream_failure(exc: Exception, *, kind: str) -> dict[str, str]:
    """502-style fetch failures: never leak raw exception text in production."""
    prod = "The target URL could not be retrieved. It may be down or blocking automated access."
    dev = f"{kind}: {exc!s}"
    return client_safe_detail(code="upstream_error", production_message=prod, developer_message=dev)
