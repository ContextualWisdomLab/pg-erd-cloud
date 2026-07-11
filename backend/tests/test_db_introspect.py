from __future__ import annotations

import pytest

from app import db_introspect


@pytest.mark.parametrize(
    "dsn,expected_dialect",
    [
        ("postgresql://u:p@db/app", "postgresql"),
        ("postgresql+asyncpg://u:p@db/app", "postgresql"),
        ("postgres://u:p@db/app", "postgresql"),
        ("postgres+psycopg2://u:p@db/app", "postgresql"),
        ("POSTGRESQL://u:p@db/app", "postgresql"),
        ("snowflake://u:p@acct/DB", "snowflake"),
        ("SNOWFLAKE://u:p@acct/DB", "snowflake"),
        ("snowflake+snowflake-connector-python://u:p@acct/DB", "snowflake"),
        ("snowflake+async://u:p@acct/DB", "snowflake"),
        ("mysql://u:p@db/app", "mysql"),
        ("mysql+pymysql://u:p@db/app", "mysql"),
        ("mariadb://u:p@db/app", "mysql"),
        ("MARIADB://u:p@db/app", "mysql"),
    ],
)
def test_detect_dsn_dialect_valid(
    dsn: str, expected_dialect: db_introspect.DatabaseDialect
) -> None:
    assert db_introspect.detect_dsn_dialect(dsn) == expected_dialect


@pytest.mark.parametrize(
    "dsn,expected_error",
    [
        ("oracle://u:p@db/app", "unsupported database DSN scheme: oracle"),
        (
            "snowflake_invalid://u:p@acct/DB",
            "unsupported database DSN scheme: <empty>",
        ),
        (
            "snowflake-connector-python://u:p@acct/DB",
            "unsupported database DSN scheme: snowflake-connector-python",
        ),
        ("http://google.com", "unsupported database DSN scheme: http"),
        ("", "unsupported database DSN scheme: <empty>"),
        ("just_a_string", "unsupported database DSN scheme: <empty>"),
    ],
)
def test_detect_dsn_dialect_invalid(dsn: str, expected_error: str) -> None:
    with pytest.raises(ValueError, match=expected_error):
        db_introspect.detect_dsn_dialect(dsn)


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

    async def fake_mysql(dsn: str, schema_filter: str | None) -> dict:
        calls.append(("mysql", dsn, schema_filter))
        return {"source_dialect": "mysql"}

    monkeypatch.setattr(db_introspect, "introspect_postgres", fake_postgres)
    monkeypatch.setattr(db_introspect, "introspect_snowflake", fake_snowflake)
    monkeypatch.setattr(db_introspect, "introspect_mysql", fake_mysql)

    assert await db_introspect.introspect_database(
        "postgresql://u:p@db/app", "public"
    ) == {"source_dialect": "postgresql"}
    assert await db_introspect.introspect_database(
        "snowflake://u:p@acct/APP/PUBLIC", None
    ) == {"source_dialect": "snowflake"}
    assert await db_introspect.introspect_database(
        "mariadb://u:p@db/app", "shop"
    ) == {"source_dialect": "mysql"}
    assert calls == [
        ("postgresql", "postgresql://u:p@db/app", "public"),
        ("snowflake", "snowflake://u:p@acct/APP/PUBLIC", None),
        ("mysql", "mariadb://u:p@db/app", "shop"),
    ]


@pytest.mark.asyncio
async def test_probe_database_dispatches_by_dialect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    async def fake_postgres(dsn: str) -> str:
        calls.append(("postgresql", dsn))
        return "postgresql 17"

    async def fake_snowflake(dsn: str) -> str:
        calls.append(("snowflake", dsn))
        return "snowflake 9"

    async def fake_mysql(dsn: str) -> str:
        calls.append(("mysql", dsn))
        return "mysql 8"

    monkeypatch.setattr(db_introspect, "probe_postgres", fake_postgres)
    monkeypatch.setattr(db_introspect, "probe_snowflake", fake_snowflake)
    monkeypatch.setattr(db_introspect, "probe_mysql", fake_mysql)

    assert (
        await db_introspect.probe_database("postgres://u:p@db/app")
        == "postgresql 17"
    )
    assert (
        await db_introspect.probe_database("snowflake://u:p@acct/APP")
        == "snowflake 9"
    )
    assert (
        await db_introspect.probe_database("mysql+pymysql://u:p@db/app") == "mysql 8"
    )
    assert calls == [
        ("postgresql", "postgres://u:p@db/app"),
        ("snowflake", "snowflake://u:p@acct/APP"),
        ("mysql", "mysql+pymysql://u:p@db/app"),
    ]


@pytest.mark.asyncio
async def test_introspect_database_redacts_password_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_postgres(dsn: str, schema_filter: str | None) -> dict:
        raise RuntimeError(
            "failed to connect to postgresql://user:supersecretpass@localhost/db"
        )

    monkeypatch.setattr(db_introspect, "introspect_postgres", fake_postgres)

    with pytest.raises(RuntimeError) as exc_info:
        await db_introspect.introspect_database(
            "postgresql://user:supersecretpass@localhost/db", None
        )

    assert "supersecretpass" not in str(exc_info.value)
    assert "postgresql://user:***@localhost/db" in str(exc_info.value)


@pytest.mark.asyncio
async def test_introspect_database_redacts_query_secret_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_postgres(dsn: str, schema_filter: str | None) -> dict:
        raise RuntimeError("driver failed with password=q/secret")

    monkeypatch.setattr(db_introspect, "introspect_postgres", fake_postgres)

    with pytest.raises(RuntimeError) as exc_info:
        await db_introspect.introspect_database(
            "postgresql://user@localhost/db?password=q%2Fsecret", None
        )

    assert "q/secret" not in str(exc_info.value)
    assert "password=***" in str(exc_info.value)
