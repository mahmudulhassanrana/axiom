from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from croniter import croniter


def validate_cron_expression(expr: str) -> None:
    """Raise ValueError if the expression is not a valid 5-field cron string."""
    base = datetime(2000, 1, 1, tzinfo=timezone.utc)
    try:
        croniter(expr.strip(), base)
    except (KeyError, ValueError) as exc:
        msg = f"Invalid cron expression: {expr!r}"
        raise ValueError(msg) from exc


def next_fire_time(cron_expression: str, after: datetime | None = None) -> datetime:
    """Next UTC fire time strictly after ``after`` (or now)."""
    now = after or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return croniter(cron_expression.strip(), now).get_next(datetime)


def cron_expression_from_source_schedule_config(cfg: dict[str, Any] | None) -> str | None:
    """Resolve a 5-field cron string from stored ``Source.schedule_config`` JSON."""
    if not cfg:
        return None
    st = cfg.get("type") or "cron"
    if st == "hourly":
        return "0 * * * *"
    if st == "daily":
        return "0 0 * * *"
    raw = cfg.get("cron_expression")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def sync_source_next_run_at(
    *,
    schedule_enabled: bool,
    schedule_paused: bool,
    is_active: bool,
    schedule_config: dict[str, Any] | None,
) -> datetime | None:
    if not schedule_enabled or schedule_paused or not is_active:
        return None
    cron_expr = cron_expression_from_source_schedule_config(schedule_config)
    if not cron_expr:
        return None
    validate_cron_expression(cron_expr)
    return next_fire_time(cron_expr)
