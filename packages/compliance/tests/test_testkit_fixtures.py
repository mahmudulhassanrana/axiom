"""Smoke tests that shared testkit fixtures are available (compliance package)."""


def test_sample_url_for_domain_checks(sample_url: str) -> None:
    assert "example.com" in sample_url
