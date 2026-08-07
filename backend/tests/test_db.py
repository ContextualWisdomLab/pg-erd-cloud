from unittest.mock import patch
from app.db import get_sync_database_url

def test_get_sync_database_url_replaces_asyncpg():
    with patch("app.db.settings.database_url", "postgresql+asyncpg://user:pass@localhost:5432/db"):
        url = get_sync_database_url()
        assert url == "postgresql+psycopg://user:pass@localhost:5432/db"

def test_get_sync_database_url_no_change_if_not_asyncpg():
    with patch("app.db.settings.database_url", "postgresql://user:pass@localhost:5432/db"):
        url = get_sync_database_url()
        assert url == "postgresql://user:pass@localhost:5432/db"

def test_get_sync_database_url_sqlite():
    with patch("app.db.settings.database_url", "sqlite:///test.db"):
        url = get_sync_database_url()
        assert url == "sqlite:///test.db"
