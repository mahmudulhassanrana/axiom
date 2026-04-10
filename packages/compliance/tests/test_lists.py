from __future__ import annotations

import pytest

from axiom_compliance.exceptions import DomainBlockedError, DomainNotAllowedError
from axiom_compliance.lists import enforce_domain_lists, host_matches_list


def test_host_matches_list_exact() -> None:
    assert host_matches_list("example.com", frozenset({"example.com"})) is True
    assert host_matches_list("other.com", frozenset({"example.com"})) is False


def test_host_matches_subdomain() -> None:
    assert host_matches_list("www.example.com", frozenset({"example.com"})) is True


def test_enforce_blocklist() -> None:
    with pytest.raises(DomainBlockedError):
        enforce_domain_lists(
            "https://evil.com/x",
            blocklist=frozenset({"evil.com"}),
            allowlist=frozenset(),
        )


def test_enforce_allowlist() -> None:
    with pytest.raises(DomainNotAllowedError):
        enforce_domain_lists(
            "https://other.com/",
            blocklist=frozenset(),
            allowlist=frozenset({"example.com"}),
        )


def test_allowlist_pass() -> None:
    h = enforce_domain_lists(
        "https://example.com/a",
        blocklist=frozenset(),
        allowlist=frozenset({"example.com"}),
    )
    assert h == "example.com"
