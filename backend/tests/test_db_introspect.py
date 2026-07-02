from __future__ import annotations

import pytest

from app import db_introspect


def test_detect_dsn_dialect_supports_postgresql_and_snowflake() -> None:
    assert db_introspect.detect_dsn_dialect("postgresql://u:p@db/app") == "postgresql"
    assert (
        db_introspect.detect_dsn_dialect("postgresql+asyncpg://u:p@db/app")
        == "postgresql"
    )
    assert db_introspect.detect_dsn_dialect("snowflake://u:p@acct/DB") == "snowflake"


def test_detect_dsn_dialect_rejects_unknown_scheme() -> None:
    with pytest.raises(ValueError, match="unsupported database DSN scheme"):
        db_introspect.detect_dsn_dialect("mysql://u:p@db/app")


@pytest.mark.asyncio
async def test_introspect_database_dispatches_by_dialect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, str | None]] = []

    async def fake_postgres(dsn: str, schema_filter: str | None) -> dict:
        calls.append(("postgresql", dsn, schema_filter))
        return {"source_dialect": "postgresql"}

    async def fake_snowflake(dsn: str, schema_filter: str | None) -> dict:
        calls.append(("snowflake", dsn, schema_filter))
        return {"source_dialect": "snowflake"}

    monkeypatch.setattr(db_introspect, "introspect_postgres", fake_postgres)
    monkeypatch.setattr(db_introspect, "introspect_snowflake", fake_snowflake)

    assert await db_introspect.introspect_database(
        "postgresql://u:p@db/app", "public"
    ) == {"source_dialect": "postgresql"}
    assert await db_introspect.introspect_database(
        "snowflake://u:p@acct/APP/PUBLIC", None
    ) == {"source_dialect": "snowflake"}
    assert calls == [
        ("postgresql", "postgresql://u:p@db/app", "public"),
        ("snowflake", "snowflake://u:p@acct/APP/PUBLIC", None),
    ]
