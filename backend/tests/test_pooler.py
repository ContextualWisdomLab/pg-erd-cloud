from __future__ import annotations

from app.pooler import (
    PoolerKind,
    build_admin_console_dsn,
    classify_pooler_version_text,
    should_route_reads_to_read_only,
)

_DUMMY_DATABASE_URL = "postgresql+asyncpg://u:dummy@localhost:5432/appdb"


import asyncio
import time
from unittest.mock import patch, MagicMock

import pytest

from app.db import get_pooler_detection
import app.db

@pytest.mark.asyncio
async def test_get_pooler_detection_concurrency(monkeypatch) -> None:
    # Set config to auto-detect
    monkeypatch.setattr(app.db.settings, "db_pooler_kind", None)
    # Clear cache
    app.db._pooler_cache = None
    app.db._pooler_cache_at = 0.0

    async def mock_probe(admin_db):
        if admin_db == "pgbouncer":
            await asyncio.sleep(0.5)
            return None
        elif admin_db == "pgcat":
            await asyncio.sleep(0.01)
            return "PgCat 0.10.0"
        return None

    monkeypatch.setattr(app.db, "_probe_pooler_admin_console", mock_probe)

    start = time.monotonic()
    result = await get_pooler_detection()
    elapsed = time.monotonic() - start

    assert result.detected is True
    assert result.kind == PoolerKind.PGCAT
    assert elapsed < 0.25, f"Took {elapsed:.2f}s, expected < 0.25s (did not run concurrently)"


def test_classify_pooler_version_text() -> None:
    assert classify_pooler_version_text("PgBouncer 1.21.0") == PoolerKind.PGBOUNCER
    assert classify_pooler_version_text("PgCat 0.10.0") == PoolerKind.PGCAT
    assert classify_pooler_version_text("something else") == PoolerKind.UNKNOWN


def test_classify_pooler_version_text_edge_cases() -> None:
    assert classify_pooler_version_text("") == PoolerKind.UNKNOWN
    assert classify_pooler_version_text("   ") == PoolerKind.UNKNOWN
    assert classify_pooler_version_text("PGBOUNCER 1.21.0") == PoolerKind.PGBOUNCER
    assert classify_pooler_version_text("PGCAT 0.10.0") == PoolerKind.PGCAT


def test_build_admin_console_dsn_strips_sqlalchemy_driver() -> None:
    dsn, password = build_admin_console_dsn(
        _DUMMY_DATABASE_URL,
        "pgbouncer",
    )
    assert dsn.startswith("postgresql://")
    assert "/pgbouncer" in dsn
    assert password == "dummy"  # noqa: S105

    # Password must not be embedded in the DSN string.
    assert ":dummy@" not in dsn


def test_should_route_reads_to_read_only() -> None:
    ro_url = "postgresql+asyncpg://u:p@localhost:5432/ro"

    assert (
        should_route_reads_to_read_only(
            mode="off", read_only_url=ro_url, pooler_detected=True
        )
        is False
    )
    assert (
        should_route_reads_to_read_only(
            mode="on", read_only_url=ro_url, pooler_detected=False
        )
        is True
    )
    assert (
        should_route_reads_to_read_only(
            mode="on", read_only_url=None, pooler_detected=True
        )
        is False
    )
    assert (
        should_route_reads_to_read_only(
            mode="auto", read_only_url=ro_url, pooler_detected=True
        )
        is True
    )
    assert (
        should_route_reads_to_read_only(
            mode="auto", read_only_url=ro_url, pooler_detected=False
        )
        is False
    )
    assert (
        should_route_reads_to_read_only(
            mode="auto", read_only_url=None, pooler_detected=True
        )
        is False
    )
