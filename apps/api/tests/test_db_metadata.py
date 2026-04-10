import axiom_api.db.models  # noqa: F401
from axiom_api.db.base import Base


def test_all_expected_tables_registered() -> None:
    names = set(Base.metadata.tables)
    assert {"organizations", "users", "sources", "jobs", "runs", "extracted_data"} <= names
