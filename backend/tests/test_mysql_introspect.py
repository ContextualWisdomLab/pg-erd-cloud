from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

import app.mysql_introspect.introspect as mysql_introspect
from app.db_introspect import detect_dsn_dialect
from app.ddl.export import snapshot_json_to_sql
from app.mysql_introspect.introspect import (
    MysqlDsnConfig,
    _introspect_sync,
    _parse_mysql_dsn,
    rows_to_snapshot,
)

TABLES = [
    {"TABLE_SCHEMA": "shop", "TABLE_NAME": "member", "TABLE_TYPE": "BASE TABLE", "TABLE_COMMENT": "회원"},
    {"TABLE_SCHEMA": "shop", "TABLE_NAME": "orders", "TABLE_TYPE": "BASE TABLE", "TABLE_COMMENT": ""},
    {"TABLE_SCHEMA": "shop", "TABLE_NAME": "v_sales", "TABLE_TYPE": "VIEW", "TABLE_COMMENT": ""},
]
COLUMNS = [
    {"TABLE_SCHEMA": "shop", "TABLE_NAME": "member", "COLUMN_NAME": "member_id", "ORDINAL_POSITION": 1,
     "COLUMN_TYPE": "bigint", "DATA_TYPE": "bigint", "IS_NULLABLE": "NO", "COLUMN_DEFAULT": None, "COLUMN_COMMENT": ""},
    {"TABLE_SCHEMA": "shop", "TABLE_NAME": "member", "COLUMN_NAME": "email", "ORDINAL_POSITION": 2,
     "COLUMN_TYPE": "varchar(255)", "DATA_TYPE": "varchar", "IS_NULLABLE": "YES", "COLUMN_DEFAULT": None, "COLUMN_COMMENT": ""},
    {"TABLE_SCHEMA": "shop", "TABLE_NAME": "orders", "COLUMN_NAME": "order_id", "ORDINAL_POSITION": 1,
     "COLUMN_TYPE": "bigint", "DATA_TYPE": "bigint", "IS_NULLABLE": "NO", "COLUMN_DEFAULT": None, "COLUMN_COMMENT": ""},
    {"TABLE_SCHEMA": "shop", "TABLE_NAME": "orders", "COLUMN_NAME": "member_id", "ORDINAL_POSITION": 2,
     "COLUMN_TYPE": "bigint", "DATA_TYPE": "bigint", "IS_NULLABLE": "NO", "COLUMN_DEFAULT": None, "COLUMN_COMMENT": ""},
]
KEY_USAGE = [
    {"CONSTRAINT_NAME": "PRIMARY", "TABLE_SCHEMA": "shop", "TABLE_NAME": "member", "COLUMN_NAME": "member_id",
     "ORDINAL_POSITION": 1, "REFERENCED_TABLE_SCHEMA": None, "REFERENCED_TABLE_NAME": None, "REFERENCED_COLUMN_NAME": None},
    {"CONSTRAINT_NAME": "PRIMARY", "TABLE_SCHEMA": "shop", "TABLE_NAME": "orders", "COLUMN_NAME": "order_id",
     "ORDINAL_POSITION": 1, "REFERENCED_TABLE_SCHEMA": None, "REFERENCED_TABLE_NAME": None, "REFERENCED_COLUMN_NAME": None},
    {"CONSTRAINT_NAME": "fk_orders_member", "TABLE_SCHEMA": "shop", "TABLE_NAME": "orders", "COLUMN_NAME": "member_id",
     "ORDINAL_POSITION": 1, "REFERENCED_TABLE_SCHEMA": "shop", "REFERENCED_TABLE_NAME": "member", "REFERENCED_COLUMN_NAME": "member_id"},
]
INDEXES = [
    {"TABLE_SCHEMA": "shop", "TABLE_NAME": "orders", "INDEX_NAME": "ix_orders_member",
     "NON_UNIQUE": 1, "SEQ_IN_INDEX": 1, "COLUMN_NAME": "member_id"},
    {"TABLE_SCHEMA": "shop", "TABLE_NAME": "member", "INDEX_NAME": "PRIMARY",
     "NON_UNIQUE": 0, "SEQ_IN_INDEX": 1, "COLUMN_NAME": "member_id"},
]


def _snap():
    return rows_to_snapshot("8.4.0", None, TABLES, COLUMNS, KEY_USAGE, INDEXES)


def test_maps_tables_views_columns():
    snap = _snap()
    kinds = {r["relation_name"]: r["relation_kind"] for r in snap["relations"]}
    assert kinds == {"member": "r", "orders": "r", "v_sales": "v"}
    email = next(c for c in snap["columns"] if c["column_name"] == "email")
    assert email["data_type"] == "varchar(255)" and email["is_not_null"] is False
    assert snap["server_version"] == "8.4.0" and snap["source_dialect"] == "mysql"


def test_maps_pks_and_fks_by_name():
    snap = _snap()
    assert {p["column_name"] for p in snap["pk_columns"]} == {"member_id", "order_id"}
    edge = snap["fk_edges"][0]
    rel = {r["relation_oid"]: r["relation_name"] for r in snap["relations"]}
    assert rel[edge["child_relation_oid"]] == "orders"
    assert rel[edge["parent_relation_oid"]] == "member"
    # constraints derived so DDL export renders PK/FK
    assert any(c["constraint_type"] == "p" for c in snap["constraints"])
    assert any(c["constraint_type"] == "f" for c in snap["constraints"])


def test_index_rows_grouped_into_defs():
    snap = _snap()
    ix = next(i for i in snap["indexes"] if i["index_name"] == "ix_orders_member")
    assert "ON shop.orders (member_id)" in ix["index_def"]
    assert ix["is_unique"] is False
    primary = next(i for i in snap["indexes"] if i["index_name"] == "PRIMARY")
    assert primary["is_primary"] is True


def test_snapshot_feeds_ddl_export_and_dialect_detection():
    ddl = snapshot_json_to_sql(_snap(), target_dialect="postgresql")
    assert 'CREATE TABLE IF NOT EXISTS "shop"."member"' in ddl
    assert "PRIMARY KEY" in ddl
    assert detect_dsn_dialect("mysql://u:p@db.example.com/shop") == "mysql"
    assert detect_dsn_dialect("mariadb://u:p@db.example.com/shop") == "mysql"


@pytest.mark.asyncio
async def test_dsn_parse_pins_validated_ip_and_rejects_bad():
    with patch(
        "app.mysql_introspect.introspect._validated_ip_hosts",
        new_callable=AsyncMock,
        return_value=["93.184.216.34"],
    ) as guard:
        cfg = await _parse_mysql_dsn("mysql://user:s3cret@db.example.com:3307/shop")
    guard.assert_awaited_once_with("db.example.com", is_hostaddr=False, port=3307)
    assert cfg.host == "93.184.216.34"  # pinned IP, not the hostname
    assert cfg.server_hostname == "db.example.com"
    assert cfg.port == 3307 and cfg.user == "user" and cfg.database == "shop"

    with pytest.raises(ValueError):
        await _parse_mysql_dsn("mysql:///nohost")
    with pytest.raises(ValueError):
        await _parse_mysql_dsn("postgres://u@h/db")


@pytest.mark.parametrize(
    "schema_filter",
    [None, "shop' OR 1=1 --"],
)
def test_introspection_binds_every_schema_filter_parameter(
    monkeypatch: pytest.MonkeyPatch,
    schema_filter: str | None,
) -> None:
    """Keep schema selection out of all four information-schema query texts."""

    queries: list[tuple[str, tuple[object, ...]]] = []

    class FakeConnection:
        """Provide the connection surface used by the synchronous introspector."""

        closed = False

        def cursor(self) -> object:
            """Return an opaque cursor consumed only by the patched fetch helper."""

            return object()

        def close(self) -> None:
            """Record deterministic connection cleanup."""

            self.closed = True

    connection = FakeConnection()

    def fake_fetch_dicts(
        _cursor: object,
        sql: str,
        params: tuple[object, ...] = (),
    ) -> list[dict[str, Any]]:
        """Capture query text and bindings without contacting a database."""

        queries.append((sql, params))
        return [{"v": "8.4.0"}] if sql == "SELECT VERSION() AS v" else []

    monkeypatch.setattr(mysql_introspect, "_connect", lambda _config: connection)
    monkeypatch.setattr(mysql_introspect, "_fetch_dicts", fake_fetch_dicts)

    config = MysqlDsnConfig(
        host="127.0.0.1",
        server_hostname="db.example.com",
        port=3306,
        user="reader",
        password=str(),
        database="catalog",
    )
    snapshot = _introspect_sync(config, schema_filter)

    expected_params = (
        schema_filter,
        "mysql",
        "information_schema",
        "performance_schema",
        "sys",
        schema_filter,
    )
    assert snapshot["schema_filter"] == schema_filter
    assert connection.closed is True
    assert queries[0] == ("SELECT VERSION() AS v", ())
    assert len(queries[1:]) == 4
    for sql, params in queries[1:]:
        assert sql.count("%s") == len(expected_params)
        assert params == expected_params
        if schema_filter is not None:
            assert schema_filter not in sql
