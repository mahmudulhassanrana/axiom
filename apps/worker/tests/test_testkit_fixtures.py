"""Smoke tests that shared testkit fixtures are available (worker package)."""


def test_sample_url_fixture(sample_url: str) -> None:
    assert sample_url.startswith("https://example.com")


def test_sample_cron_and_timezone(sample_cron_expression: str, sample_timezone: str) -> None:
    assert len(sample_cron_expression.split()) >= 5
    assert sample_timezone
