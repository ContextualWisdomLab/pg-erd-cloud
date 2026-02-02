from __future__ import annotations

from collections.abc import AsyncGenerator
import asyncio
import math
import time

import psycopg
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.settings import settings
from app.pooler import (
    PoolerDetectionResult,
    PoolerKind,
    build_admin_console_dsn,
    classify_pooler_version_text,
    should_route_reads_to_read_only,
)


def get_sync_database_url() -> str:
    """Return a sync database URL for Alembic.

    Alembic uses a synchronous engine; convert an async SQLAlchemy URL to a
    compatible sync URL.
    """

    # Alembic uses sync engine; convert async URL.
    url = settings.database_url
    if url.startswith("postgresql+asyncpg://"):
        # Prefer psycopg (v3) for sync migrations.
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return url


engine: AsyncEngine = create_async_engine(
    settings.database_url, pool_pre_ping=True
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

read_only_engine: AsyncEngine | None = (
    create_async_engine(settings.database_read_only_url, pool_pre_ping=True)
    if settings.database_read_only_url
    else None
)
ReadOnlySessionLocal = (
    async_sessionmaker(read_only_engine, expire_on_commit=False)
    if read_only_engine is not None
    else None
)


_POOLER_CACHE_TTL_SECONDS = 300.0
_pooler_cache: PoolerDetectionResult | None = None
_pooler_cache_at: float = 0.0
_pooler_lock = asyncio.Lock()


async def _probe_pooler_admin_console(admin_db: str) -> str | None:
    """Best-effort probe for pooler admin console.

    Uses psycopg in a thread because some pooler admin consoles only support the
    simple query protocol.
    """

    dsn, password = build_admin_console_dsn(settings.database_url, admin_db)

    raw_timeout = float(settings.db_pooler_probe_timeout_seconds)
    if raw_timeout <= 0.0:
        return None

    # libpq's connect_timeout is specified in whole seconds.
    # Note: some PostgreSQL/libpq versions effectively treat values < 2 as 2.
    timeout_seconds = max(2, int(math.ceil(raw_timeout)))

    def _run() -> str | None:
        with psycopg.connect(
            dsn,
            password=password,
            connect_timeout=str(timeout_seconds),
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SHOW VERSION;")
                row = cur.fetchone()
                if not row or row[0] is None:
                    return None
                return str(row[0])

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_run), timeout=float(timeout_seconds) + 0.2
        )
    except Exception:  # noqa: BLE001
        return None


async def get_pooler_detection() -> PoolerDetectionResult:
    """Return a cached best-effort pooler detection result."""

    global _pooler_cache_at
    global _pooler_cache

    # Fast path: honor explicit configuration.
    if settings.db_pooler_kind is not None:
        kind = PoolerKind(settings.db_pooler_kind)
        detected = kind is not PoolerKind.NONE
        return PoolerDetectionResult(
            kind=kind, detected=detected, version_text=None
        )

    now = time.monotonic()
    if (
        _pooler_cache is not None
        and (now - _pooler_cache_at) < _POOLER_CACHE_TTL_SECONDS
    ):
        return _pooler_cache

    async with _pooler_lock:
        now2 = time.monotonic()
        if (
            _pooler_cache is not None
            and (now2 - _pooler_cache_at) < _POOLER_CACHE_TTL_SECONDS
        ):
            return _pooler_cache

        # Try PgBouncer first, then PgCat.
        for admin_db in ("pgbouncer", "pgcat"):
            version_text = await _probe_pooler_admin_console(admin_db)
            if version_text:
                kind = classify_pooler_version_text(version_text)
                _pooler_cache = PoolerDetectionResult(
                    kind=kind, detected=True, version_text=version_text
                )
                _pooler_cache_at = time.monotonic()
                return _pooler_cache

        _pooler_cache = PoolerDetectionResult(
            kind=PoolerKind.UNKNOWN, detected=False, version_text=None
        )
        _pooler_cache_at = time.monotonic()
        return _pooler_cache


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession."""
    async with SessionLocal() as session:
        yield session


async def get_read_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a read session.

    - If DATABASE_READ_ONLY_URL is not configured, it falls back to the primary
      session.
    - If DB_READ_ROUTING=auto, it uses the read-only DSN only when a pooler is
      detected (or explicitly hinted).
    """

    if ReadOnlySessionLocal is None:
        async with SessionLocal() as session:
            yield session
        return

    detection = await get_pooler_detection()
    use_read_only = should_route_reads_to_read_only(
        mode=settings.db_read_routing,
        read_only_url=settings.database_read_only_url,
        pooler_detected=detection.detected,
    )

    maker = ReadOnlySessionLocal if use_read_only else SessionLocal
    async with maker() as session:
        yield session
