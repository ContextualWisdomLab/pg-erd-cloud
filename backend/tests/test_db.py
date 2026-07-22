from __future__ import annotations

import time
import asyncio
from unittest.mock import patch, MagicMock

import pytest

from app.db import (
    get_sync_database_url,
    _probe_pooler_admin_console,
    get_pooler_detection,
    get_session,
    get_read_session,
)
from app.pooler import PoolerDetectionResult, PoolerKind
from app.settings import settings


def test_get_sync_database_url():
    with patch("app.db.settings", database_url="postgresql+asyncpg://user:pass@host/db"):
        assert get_sync_database_url() == "postgresql+psycopg://user:pass@host/db"

    with patch("app.db.settings", database_url="sqlite:///test.db"):
        assert get_sync_database_url() == "sqlite:///test.db"

@pytest.mark.asyncio
async def test_probe_pooler_admin_console_timeout():
    with patch("app.db.settings", db_pooler_probe_timeout_seconds=0.0, database_url="postgresql+asyncpg://user:pass@host/db"):
        res = await _probe_pooler_admin_console("pgbouncer")
        assert res is None

@pytest.mark.asyncio
async def test_probe_pooler_admin_console_success():
    class DummyCursor:
        def execute(self, q): pass
        def fetchone(self): return ("PgBouncer 1.21.0",)
        def __enter__(self): return self
        def __exit__(self, *args): pass

    class DummyConn:
        def cursor(self): return DummyCursor()
        def __enter__(self): return self
        def __exit__(self, *args): pass

    with patch("app.db.settings", db_pooler_probe_timeout_seconds=2.0, database_url="postgresql+asyncpg://user:pass@host/db"):
        with patch("psycopg.connect", return_value=DummyConn()):
            res = await _probe_pooler_admin_console("pgbouncer")
            assert res == "PgBouncer 1.21.0"

@pytest.mark.asyncio
async def test_probe_pooler_admin_console_none():
    class DummyCursor:
        def execute(self, q): pass
        def fetchone(self): return None
        def __enter__(self): return self
        def __exit__(self, *args): pass

    class DummyConn:
        def cursor(self): return DummyCursor()
        def __enter__(self): return self
        def __exit__(self, *args): pass

    with patch("app.db.settings", db_pooler_probe_timeout_seconds=2.0, database_url="postgresql+asyncpg://user:pass@host/db"):
        with patch("psycopg.connect", return_value=DummyConn()):
            res = await _probe_pooler_admin_console("pgbouncer")
            assert res is None

@pytest.mark.asyncio
async def test_probe_pooler_admin_console_exception():
    with patch("app.db.settings", db_pooler_probe_timeout_seconds=2.0, database_url="postgresql+asyncpg://user:pass@host/db"):
        with patch("psycopg.connect", side_effect=Exception("Timeout or fail")):
            res = await _probe_pooler_admin_console("pgbouncer")
            assert res is None


@pytest.fixture(autouse=True)
def reset_pooler_cache():
    import app.db
    app.db._pooler_cache = None
    app.db._pooler_cache_at = 0.0
    yield
    app.db._pooler_cache = None
    app.db._pooler_cache_at = 0.0

@pytest.mark.asyncio
async def test_get_pooler_detection_explicit():
    with patch("app.db.settings", db_pooler_kind="pgbouncer"):
        res = await get_pooler_detection()
        assert res.kind == PoolerKind.PGBOUNCER
        assert res.detected is True

@pytest.mark.asyncio
async def test_get_pooler_detection_cached():
    import app.db
    app.db._pooler_cache = PoolerDetectionResult(PoolerKind.PGCAT, True, "PgCat 0.1")
    app.db._pooler_cache_at = time.monotonic()

    with patch("app.db.settings", db_pooler_kind=None):
        res = await get_pooler_detection()
        assert res.kind == PoolerKind.PGCAT

@pytest.mark.asyncio
async def test_get_pooler_detection_pgbouncer():
    with patch("app.db.settings", db_pooler_kind=None):
        with patch("app.db._probe_pooler_admin_console", side_effect=lambda db: "PgBouncer 1.21.0" if db == "pgbouncer" else None):
            res = await get_pooler_detection()
            assert res.kind == PoolerKind.PGBOUNCER

@pytest.mark.asyncio
async def test_get_pooler_detection_pgcat():
    with patch("app.db.settings", db_pooler_kind=None):
        with patch("app.db._probe_pooler_admin_console", side_effect=lambda db: "PgCat 0.10.0" if db == "pgcat" else None):
            res = await get_pooler_detection()
            assert res.kind == PoolerKind.PGCAT

@pytest.mark.asyncio
async def test_get_pooler_detection_unknown():
    with patch("app.db.settings", db_pooler_kind=None):
        with patch("app.db._probe_pooler_admin_console", return_value=None):
            res = await get_pooler_detection()
            assert res.kind == PoolerKind.UNKNOWN

@pytest.mark.asyncio
async def test_get_session():
    async for session in get_session():
        assert session is not None
        break

@pytest.mark.asyncio
async def test_get_read_session_no_readonly():
    import app.db
    orig = app.db.ReadOnlySessionLocal
    app.db.ReadOnlySessionLocal = None
    try:
        async for session in get_read_session():
            assert session is not None
            break
    finally:
        app.db.ReadOnlySessionLocal = orig

@pytest.mark.asyncio
async def test_get_read_session_with_readonly():
    import app.db
    app.db.ReadOnlySessionLocal = MagicMock()
    app.db.ReadOnlySessionLocal.return_value.__aenter__.return_value = "readonly_session"
    app.db.SessionLocal = MagicMock()
    app.db.SessionLocal.return_value.__aenter__.return_value = "primary_session"

    with patch("app.db.get_pooler_detection", return_value=PoolerDetectionResult(PoolerKind.PGBOUNCER, True, "PgBouncer")):
        with patch("app.db.should_route_reads_to_read_only", return_value=True):
            async for session in get_read_session():
                assert session == "readonly_session"
                break

        with patch("app.db.should_route_reads_to_read_only", return_value=False):
            async for session in get_read_session():
                assert session == "primary_session"
                break

@pytest.mark.asyncio
async def test_get_pooler_detection_locked_cache():
    import app.db
    with patch("app.db.settings", db_pooler_kind=None):
        with patch("app.db._probe_pooler_admin_console", return_value="PgBouncer 1.21.0"):
            async def fast_cache():
                app.db._pooler_cache = PoolerDetectionResult(PoolerKind.PGCAT, True, "PgCat 0.1")
                app.db._pooler_cache_at = time.monotonic()

            # Pretend that by the time lock is acquired, cache is populated
            original_lock = app.db._pooler_lock
            class MockLock:
                async def __aenter__(self):
                    await fast_cache()
                    return self
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass

            app.db._pooler_lock = MockLock()
            try:
                res = await get_pooler_detection()
                assert res.kind == PoolerKind.PGCAT
            finally:
                app.db._pooler_lock = original_lock

@pytest.mark.asyncio
async def test_get_read_session_return():
    import app.db
    orig = app.db.ReadOnlySessionLocal
    app.db.ReadOnlySessionLocal = None
    try:
        gen = get_read_session()
        await gen.__anext__()
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass
    finally:
        app.db.ReadOnlySessionLocal = orig
