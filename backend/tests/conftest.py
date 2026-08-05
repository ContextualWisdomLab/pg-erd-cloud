"""Test defaults.

The application settings use required environment variables (DATABASE_URL,
APP_SECRET). Unit tests set safe dummy defaults so modules that import settings
can be imported without needing a local .env.
"""

from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test_user:test_password@127.0.0.1:5432/test_db",
)
os.environ.setdefault("APP_SECRET", "test-secret")
import pytest
from unittest.mock import MagicMock

@pytest.fixture(autouse=True)
def mock_pyjwk(monkeypatch):
    import app.auth as auth

    class DummyKey:
        key = "dummy"

    def dummy_pyjwk(jwk):
        return DummyKey()

    if hasattr(auth.jwt, 'PyJWK'):
        monkeypatch.setattr(auth.jwt, 'PyJWK', dummy_pyjwk)
