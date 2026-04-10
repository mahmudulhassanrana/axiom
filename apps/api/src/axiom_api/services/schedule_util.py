from __future__ import annotations

from datetime import datetime, timezone

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
