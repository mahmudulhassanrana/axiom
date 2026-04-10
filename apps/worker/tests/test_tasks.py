from axiom_worker.tasks import ping


def test_ping_run() -> None:
    assert ping.run() == "pong"
