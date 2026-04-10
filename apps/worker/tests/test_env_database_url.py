import os
from pathlib import Path

import pytest

from axiom_worker.env import (
    _bootstrap_database_url_for_repo,
    _parse_database_url_line_from_env_file,
    ensure_database_url_from_env_files,
)


def test_parse_database_url_last_wins(tmp_path: Path) -> None:
    p = tmp_path / ".env"
    p.write_text(
        "DATABASE_URL=first\n# c\nDATABASE_URL=postgresql+asyncpg://u:@127.0.0.1:5/db\n",
        encoding="utf-8",
    )
    assert _parse_database_url_line_from_env_file(p) == "postgresql+asyncpg://u:@127.0.0.1:5/db"


def test_bootstrap_merges_three_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = tmp_path / "r"
    (repo / "apps" / "api").mkdir(parents=True)
    (repo / "apps" / "worker").mkdir(parents=True)
    (repo / ".env").write_text("DATABASE_URL=postgresql://one/db\n", encoding="utf-8")
    (repo / "apps" / "api" / ".env").write_text("DATABASE_URL=postgresql://two/db\n", encoding="utf-8")

    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert _bootstrap_database_url_for_repo(repo) is True
    assert os.environ.get("DATABASE_URL") == "postgresql://two/db"
    os.environ.pop("DATABASE_URL", None)


def test_ensure_uses_axiom_repo_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo = tmp_path / "r"
    (repo / "apps" / "api").mkdir(parents=True)
    (repo / "apps" / "worker").mkdir(parents=True)
    (repo / ".env").write_text("DATABASE_URL=postgresql://from-axiom-root/x\n", encoding="utf-8")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("AXIOM_REPO_ROOT", str(repo))

    ensure_database_url_from_env_files()

    assert os.environ.get("DATABASE_URL") == "postgresql://from-axiom-root/x"
    os.environ.pop("DATABASE_URL", None)
    monkeypatch.delenv("AXIOM_REPO_ROOT", raising=False)
