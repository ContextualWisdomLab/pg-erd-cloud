from __future__ import annotations

import asyncio

import pytest

import app.db
from app.pooler import (
    PoolerKind,
    build_admin_console_dsn,
    classify_pooler_version_text,
    should_route_reads_to_read_only,
)

_DUMMY_DATABASE_URL = "postgresql+asyncpg://u:dummy@localhost:5432/appdb"


@pytest.mark.asyncio
async def test_get_pooler_detection_returns_first_success_and_awaits_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return the first successful probe after cancelling and joining its peer."""

    monkeypatch.setattr(app.db.settings, "db_pooler_kind", None)
    app.db._pooler_cache = None
    app.db._pooler_cache_at = 0.0
    slow_started = asyncio.Event()
    slow_cancelled = asyncio.Event()
    never_finishes = asyncio.Event()

    async def mock_probe(admin_db: str) -> str | None:
        if admin_db == "pgcat":
            await slow_started.wait()
            return "PgCat 0.10.0"
        slow_started.set()
        try:
            await never_finishes.wait()
        except asyncio.CancelledError:
            slow_cancelled.set()
            raise

    monkeypatch.setattr(app.db, "_probe_pooler_admin_console", mock_probe)

    result = await app.db.get_pooler_detection()

    assert result.detected is True
    assert result.kind == PoolerKind.PGCAT
    assert slow_cancelled.is_set()


@pytest.mark.asyncio
async def test_get_pooler_detection_waits_past_a_fast_negative_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Continue probing when the first completed admin console is not a pooler."""

    monkeypatch.setattr(app.db.settings, "db_pooler_kind", None)
    app.db._pooler_cache = None
    app.db._pooler_cache_at = 0.0
    first_finished = asyncio.Event()

    async def mock_probe(admin_db: str) -> str | None:
        if admin_db == "pgbouncer":
            first_finished.set()
            return None
        await first_finished.wait()
        return "PgCat 0.10.0"

    monkeypatch.setattr(app.db, "_probe_pooler_admin_console", mock_probe)

    result = await app.db.get_pooler_detection()

    assert result.detected is True
    assert result.kind == PoolerKind.PGCAT


@pytest.mark.asyncio
async def test_get_pooler_detection_awaits_probe_cleanup_on_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settle every child probe before propagating caller cancellation."""

    monkeypatch.setattr(app.db.settings, "db_pooler_kind", None)
    app.db._pooler_cache = None
    app.db._pooler_cache_at = 0.0
    both_started = asyncio.Event()
    never_finishes = asyncio.Event()
    started: set[str] = set()
    cleaned: set[str] = set()

    async def mock_probe(admin_db: str) -> str | None:
        started.add(admin_db)
        if len(started) == 2:
            both_started.set()
        try:
            await never_finishes.wait()
        finally:
            cleaned.add(admin_db)

    monkeypatch.setattr(app.db, "_probe_pooler_admin_console", mock_probe)
    detection = asyncio.create_task(app.db.get_pooler_detection())
    await both_started.wait()

    detection.cancel()
    with pytest.raises(asyncio.CancelledError):
        await detection

    assert cleaned == {"pgbouncer", "pgcat"}


@pytest.mark.asyncio
async def test_get_pooler_detection_tolerates_probe_errors_and_caches_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return bounded unknown evidence after every concurrent probe fails."""

    monkeypatch.setattr(app.db.settings, "db_pooler_kind", None)
    app.db._pooler_cache = None
    app.db._pooler_cache_at = 0.0

    async def mock_probe(admin_db: str) -> str | None:
        if admin_db == "pgbouncer":
            raise RuntimeError("private connection detail")
        return None

    monkeypatch.setattr(app.db, "_probe_pooler_admin_console", mock_probe)

    result = await app.db.get_pooler_detection()

    assert result == app.db.PoolerDetectionResult(
        kind=PoolerKind.UNKNOWN,
        detected=False,
        version_text=None,
    )
    assert app.db._pooler_cache == result
    assert app.db._pooler_cache_at > 0.0


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
