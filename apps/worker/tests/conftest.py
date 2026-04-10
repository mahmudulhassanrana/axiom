import pytest

from axiom_worker.celery_app import app as celery_app


@pytest.fixture(autouse=True)
def _disable_compliance_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPLIANCE_ENABLED", "false")


@pytest.fixture
def celery_eager():
    prev_eager = celery_app.conf.task_always_eager
    prev_prop = celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield celery_app
    celery_app.conf.task_always_eager = prev_eager
    celery_app.conf.task_eager_propagates = prev_prop
