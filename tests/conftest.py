"""Every test must explicitly supply isolated storage."""
import pytest
from jobtrack import database

@pytest.fixture(autouse=True)
def prohibit_production_database(monkeypatch):
    def forbidden():
        raise AssertionError("Tests must not resolve the production database")
    monkeypatch.setattr(database, "get_database_path", forbidden)
