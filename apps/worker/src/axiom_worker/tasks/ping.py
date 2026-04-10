from axiom_worker.celery_app import app


@app.task(name="axiom.ping")
def ping() -> str:
    return "pong"
