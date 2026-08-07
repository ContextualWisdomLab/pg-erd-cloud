"""Behavioral coverage for database routing and pooler detection boundaries."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from app import db
from app.pooler import PoolerDetectionResult, PoolerKind
from app.settings import settings


class _Cursor:
    """Synchronous psycopg cursor double for pooler probes."""

    def __init__(self, row: tuple[object | None] | None) -> None:
        self.row = row
        self.statement: str | None = None

    def __enter__(self) -> "_Cursor":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, statement: str) -> None:
        self.statement = statement

    def fetchone(self) -> tuple[object | None] | None:
        return self.row


class _Connection:
    """Synchronous psycopg connection double exposing one cursor."""

    def __init__(self, row: tuple[object | None] | None) -> None:
        self.cursor_value = _Cursor(row)

    def __enter__(self) -> "_Connection":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def cursor(self) -> _Cursor:
        return self.cursor_value


class _AsyncSessionContext:
    """Async context manager carrying a stable session marker."""

    def __init__(self, marker: str) -> None:
        self.marker = marker

    async def __aenter__(self) -> "_AsyncSessionContext":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


class _MonotonicClock:
    """Module-like monotonic clock that never exhausts its final value."""

    def __init__(self, *values: float) -> None:
        if not values:
            raise ValueError("at least one monotonic value is required")
        self._values = list(values)

    def monotonic(self) -> float:
        """Return each configured value once, then repeat the final value."""
        if len(self._values) > 1:
            return self._values.pop(0)
        return self._values[0]


def _maker(marker: str):  # type: ignore[no-untyped-def]
    """Return a zero-argument async-session factory for generator tests."""

    def factory() -> _AsyncSessionContext:
        return _AsyncSessionContext(marker)

    return factory


def test_get_sync_database_url_converts_only_asyncpg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Convert asyncpg URLs for Alembic while preserving already-sync URLs."""
    monkeypatch.setattr(
        settings,
        "database_url",
        "postgresql+asyncpg://user:pass@localhost:5432/appdb",
    )
    assert (
        db.get_sync_database_url()
        == "postgresql+psycopg://user:pass@localhost:5432/appdb"
    )

    monkeypatch.setattr(
        settings,
        "database_url",
        "postgresql://user:pass@localhost:5432/appdb",
    )
    assert db.get_sync_database_url() == "postgresql://user:pass@localhost:5432/appdb"


@pytest.mark.asyncio
async def test_probe_pooler_admin_console_handles_disabled_empty_and_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bound pooler probes and normalize missing or present SHOW VERSION rows."""
    monkeypatch.setattr(
        db,
        "build_admin_console_dsn",
        lambda *_args: ("postgresql://u@db/p", "pw"),
    )
    monkeypatch.setattr(settings, "db_pooler_probe_timeout_seconds", 0.0)
    assert await db._probe_pooler_admin_console("pgbouncer") is None

    monkeypatch.setattr(settings, "db_pooler_probe_timeout_seconds", 0.1)
    observed: list[tuple[str, str | None, int]] = []

    def connect_empty(
        dsn: str,
        *,
        password: str | None,
        connect_timeout: int,
    ) -> _Connection:
        observed.append((dsn, password, connect_timeout))
        return _Connection(None)

    monkeypatch.setattr(db.psycopg, "connect", connect_empty)
    assert await db._probe_pooler_admin_console("pgbouncer") is None
    assert observed == [("postgresql://u@db/p", "pw", 2)]

    def connect_version(
        _dsn: str,
        *,
        password: str | None,
        connect_timeout: int,
    ) -> _Connection:
        assert password == "pw"
        assert connect_timeout == 2
        return _Connection(("PgBouncer 1.24.0",))

    monkeypatch.setattr(db.psycopg, "connect", connect_version)
    assert await db._probe_pooler_admin_console("pgbouncer") == "PgBouncer 1.24.0"


@pytest.mark.asyncio
async def test_probe_pooler_admin_console_redacts_probe_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Treat transport/runtime failures as absence rather than leaking details."""
    monkeypatch.setattr(
        db,
        "build_admin_console_dsn",
        lambda *_args: ("postgresql://u@db/p", None),
    )
    monkeypatch.setattr(settings, "db_pooler_probe_timeout_seconds", 1.1)

    def failing_connect(*_args: object, **_kwargs: object) -> _Connection:
        raise RuntimeError("private connection detail")

    monkeypatch.setattr(db.psycopg, "connect", failing_connect)
    assert await db._probe_pooler_admin_console("pgcat") is None


@pytest.mark.asyncio
async def test_get_pooler_detection_honors_explicit_and_cached_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use explicit configuration and both cache paths before network probing."""
    monkeypatch.setattr(settings, "db_pooler_kind", "pgbouncer")
    detected = await db.get_pooler_detection()
    assert detected == PoolerDetectionResult(PoolerKind.PGBOUNCER, True, None)

    monkeypatch.setattr(settings, "db_pooler_kind", "none")
    disabled = await db.get_pooler_detection()
    assert disabled == PoolerDetectionResult(PoolerKind.NONE, False, None)

    monkeypatch.setattr(settings, "db_pooler_kind", None)
    cached = PoolerDetectionResult(PoolerKind.PGCAT, True, "PgCat 1")
    monkeypatch.setattr(db, "_pooler_cache", cached)
    monkeypatch.setattr(db, "_pooler_cache_at", 50.0)
    monkeypatch.setattr(db, "time", _MonotonicClock(100.0))
    assert await db.get_pooler_detection() is cached

    monkeypatch.setattr(db, "_pooler_cache_at", 0.0)
    monkeypatch.setattr(db, "time", _MonotonicClock(400.0, 100.0))
    assert await db.get_pooler_detection() is cached


@pytest.mark.asyncio
async def test_get_pooler_detection_probes_in_order_and_caches_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Probe PgBouncer before PgCat and persist positive or negative evidence."""
    monkeypatch.setattr(settings, "db_pooler_kind", None)
    monkeypatch.setattr(db, "_pooler_cache", None)
    monkeypatch.setattr(db, "_pooler_cache_at", 0.0)
    monkeypatch.setattr(db, "time", _MonotonicClock(1000.0))
    calls: list[str] = []

    async def probe(admin_db: str) -> str | None:
        calls.append(admin_db)
        return "PgCat 0.4.0" if admin_db == "pgcat" else None

    monkeypatch.setattr(db, "_probe_pooler_admin_console", probe)
    detected = await db.get_pooler_detection()
    assert calls == ["pgbouncer", "pgcat"]
    assert detected.kind is PoolerKind.PGCAT
    assert detected.detected is True
    assert detected.version_text == "PgCat 0.4.0"

    monkeypatch.setattr(db, "_pooler_cache", None)
    calls.clear()

    async def absent(admin_db: str) -> None:
        calls.append(admin_db)
        return None

    monkeypatch.setattr(db, "_probe_pooler_admin_console", absent)
    missing = await db.get_pooler_detection()
    assert calls == ["pgbouncer", "pgcat"]
    assert missing == PoolerDetectionResult(PoolerKind.UNKNOWN, False, None)


@pytest.mark.asyncio
async def test_database_session_generators_choose_primary_and_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Yield the primary session by default and route eligible reads separately."""
    monkeypatch.setattr(db, "SessionLocal", _maker("primary"))
    monkeypatch.setattr(db, "ReadOnlySessionLocal", None)

    primary_generator: AsyncIterator[object] = db.get_session()
    primary = await anext(primary_generator)
    assert primary.marker == "primary"  # type: ignore[attr-defined]
    await primary_generator.aclose()

    fallback_generator: AsyncIterator[object] = db.get_read_session()
    fallback = await anext(fallback_generator)
    assert fallback.marker == "primary"  # type: ignore[attr-defined]
    await fallback_generator.aclose()

    monkeypatch.setattr(db, "ReadOnlySessionLocal", _maker("read-only"))
    monkeypatch.setattr(
        settings,
        "database_read_only_url",
        "postgresql+asyncpg://ro/db",
    )
    monkeypatch.setattr(settings, "db_read_routing", "auto")

    async def detected_pooler() -> PoolerDetectionResult:
        return PoolerDetectionResult(PoolerKind.PGBOUNCER, True, "PgBouncer")

    monkeypatch.setattr(db, "get_pooler_detection", detected_pooler)
    read_generator: AsyncIterator[object] = db.get_read_session()
    read_only = await anext(read_generator)
    assert read_only.marker == "read-only"  # type: ignore[attr-defined]
    await read_generator.aclose()

    async def no_pooler() -> PoolerDetectionResult:
        return PoolerDetectionResult(PoolerKind.UNKNOWN, False, None)

    monkeypatch.setattr(db, "get_pooler_detection", no_pooler)
    routed_primary_generator: AsyncIterator[object] = db.get_read_session()
    routed_primary = await anext(routed_primary_generator)
    assert routed_primary.marker == "primary"  # type: ignore[attr-defined]
    await routed_primary_generator.aclose()
