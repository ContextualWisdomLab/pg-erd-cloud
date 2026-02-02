from __future__ import annotations

from app.pooler import (
    PoolerKind,
    build_admin_console_dsn,
    classify_pooler_version_text,
    should_route_reads_to_read_only,
)

_DUMMY_DATABASE_URL = (
    "postgresql+asyncpg://u:dummy@localhost:5432/appdb"  # noqa: S105
)


def test_classify_pooler_version_text() -> None:
    assert (
        classify_pooler_version_text("PgBouncer 1.21.0") == PoolerKind.PGBOUNCER
    )
    assert classify_pooler_version_text("PgCat 0.10.0") == PoolerKind.PGCAT
    assert classify_pooler_version_text("something else") == PoolerKind.UNKNOWN


def test_build_admin_console_dsn_strips_sqlalchemy_driver() -> None:
    dsn, password = build_admin_console_dsn(
        _DUMMY_DATABASE_URL,
        "pgbouncer",
    )
    assert dsn.startswith("postgresql://")
    assert "/pgbouncer" in dsn
    assert password == "dummy"

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
