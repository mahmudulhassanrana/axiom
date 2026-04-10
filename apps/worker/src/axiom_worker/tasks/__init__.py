"""Register Celery tasks (import side effects)."""

from axiom_worker.tasks.ping import ping
from axiom_worker.tasks.scrape import scrape_task
from axiom_worker.tasks.tick_schedules import tick_schedules

__all__ = ["ping", "scrape_task", "tick_schedules"]
