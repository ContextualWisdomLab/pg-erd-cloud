from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.settings import settings


def get_sync_database_url() -> str:
    # Alembic uses sync engine; convert async URL.
    url = settings.database_url
    if url.startswith("postgresql+asyncpg://"):
        # Prefer psycopg (v3) for sync migrations.
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return url


engine: AsyncEngine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
