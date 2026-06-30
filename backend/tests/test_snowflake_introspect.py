from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from app.snowflake_introspect.introspect import (
    _parse_snowflake_dsn,
    introspect_snowflake,
)


class FakeCursor:
    def __init__(self) -> None:
        self.description: list[tuple[str]] = []
        self._rows: list[tuple[object, ...]] = []
        self.closed = False

    def execute(self, sql: str, params: Sequence[object] = ()) -> None:
        rows = fake_rows_for_query(sql, params)
        columns = list(rows[0].keys()) if rows else ["empty"]
        self.description = [(column,) for column in columns]
        self._rows = [tuple(row.get(column) for column in columns) for row in rows]

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def close(self) -> None:
        self.closed = True


def fake_rows_for_query(sql: str, params: Sequence[object]) -> list[dict[str, object]]:
    schema_filter = params[0] if params else None
    assert schema_filter in (None, "PUBLIC")

    if "CURRENT_VERSION" in sql:
        return [{"server_version": "8.30.1"}]
    if "information_schema.schemata" in sql:
        return [{"schema_name": "PUBLIC"}]
    if "information_schema.tables" in sql:
        return [
            {
                "table_schema": "PUBLIC",
                "table_name": "CUSTOMERS",
                "table_type": "BASE TABLE",
                "comment": "Customer master",
            },
            {
                "table_schema": "PUBLIC",
                "table_name": "ORDERS",
                "table_type": "BASE TABLE",
                "comment": None,
            },
        ]
    if "information_schema.columns" in sql:
        return [
            {
                "table_schema": "PUBLIC",
                "table_name": "CUSTOMERS",
                "ordinal_position": 1,
                "column_name": "CUSTOMER_ID",
                "data_type": "NUMBER",
                "character_maximum_length": None,
                "numeric_precision": 38,
                "numeric_scale": 0,
                "datetime_precision": None,
                "is_nullable": "NO",
                "column_default": None,
                "comment": "Synthetic key",
            },
            {
                "table_schema": "PUBLIC",
                "table_name": "CUSTOMERS",
                "ordinal_position": 2,
                "column_name": "EMAIL",
                "data_type": "VARCHAR",
                "character_maximum_length": 100,
                "numeric_precision": None,
                "numeric_scale": None,
                "datetime_precision": None,
                "is_nullable": "YES",
                "column_default": None,
                "comment": None,
            },
            {
                "table_schema": "PUBLIC",
                "table_name": "ORDERS",
                "ordinal_position": 1,
                "column_name": "ORDER_ID",
                "data_type": "NUMBER",
                "character_maximum_length": None,
                "numeric_precision": 38,
                "numeric_scale": 0,
                "datetime_precision": None,
                "is_nullable": "NO",
                "column_default": None,
                "comment": None,
            },
            {
                "table_schema": "PUBLIC",
                "table_name": "ORDERS",
                "ordinal_position": 2,
                "column_name": "CUSTOMER_ID",
                "data_type": "NUMBER",
                "character_maximum_length": None,
                "numeric_precision": 38,
                "numeric_scale": 0,
                "datetime_precision": None,
                "is_nullable": "NO",
                "column_default": None,
                "comment": None,
            },
            {
                "table_schema": "PUBLIC",
                "table_name": "ORDERS",
                "ordinal_position": 3,
                "column_name": "CREATED_AT",
                "data_type": "TIMESTAMP_NTZ",
                "character_maximum_length": None,
                "numeric_precision": None,
                "numeric_scale": None,
                "datetime_precision": 9,
                "is_nullable": "YES",
                "column_default": "CURRENT_TIMESTAMP()",
                "comment": None,
            },
        ]
    if "information_schema.table_constraints" in sql:
        return [
            {
                "constraint_schema": "PUBLIC",
                "constraint_name": "CUSTOMERS_PK",
                "constraint_type": "PRIMARY KEY",
                "table_schema": "PUBLIC",
                "table_name": "CUSTOMERS",
                "column_name": "CUSTOMER_ID",
                "ordinal_position": 1,
                "referenced_table_schema": None,
                "referenced_table_name": None,
                "referenced_column_name": None,
            },
            {
                "constraint_schema": "PUBLIC",
                "constraint_name": "ORDERS_PK",
                "constraint_type": "PRIMARY KEY",
                "table_schema": "PUBLIC",
                "table_name": "ORDERS",
                "column_name": "ORDER_ID",
                "ordinal_position": 1,
                "referenced_table_schema": None,
                "referenced_table_name": None,
                "referenced_column_name": None,
            },
            {
                "constraint_schema": "PUBLIC",
                "constraint_name": "ORDERS_CUSTOMER_FK",
                "constraint_type": "FOREIGN KEY",
                "table_schema": "PUBLIC",
                "table_name": "ORDERS",
                "column_name": "CUSTOMER_ID",
                "ordinal_position": 1,
                "referenced_table_schema": "PUBLIC",
                "referenced_table_name": "CUSTOMERS",
                "referenced_column_name": "CUSTOMER_ID",
            },
        ]
    return []


@pytest.mark.asyncio
async def test_parse_snowflake_dsn_rejects_connector_overrides() -> None:
    with pytest.raises(ValueError, match="unsupported Snowflake DSN query parameter"):
        await _parse_snowflake_dsn("snowflake://user:pass@acct/DB/PUBLIC?host=evil")


@pytest.mark.asyncio
async def test_parse_snowflake_dsn_validates_authenticator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_validated_ip_hosts(host, is_hostaddr, port):
        return (host,)

    monkeypatch.setattr(
        "app.snowflake_introspect.introspect._validated_ip_hosts",
        fake_validated_ip_hosts,
    )

    # Allowed okta URLs
    conf = await _parse_snowflake_dsn(
        "snowflake://user:pass@acct/DB/PUBLIC?authenticator=https://company.okta.com"
    )
    assert conf.authenticator == "https://company.okta.com"

    # Allowed safe string values
    conf = await _parse_snowflake_dsn(
        "snowflake://user:pass@acct/DB/PUBLIC?authenticator=externalbrowser"
    )
    assert conf.authenticator == "externalbrowser"

    # Rejected unknown strings
    with pytest.raises(ValueError, match="unsupported Snowflake authenticator value"):
        await _parse_snowflake_dsn(
            "snowflake://user:pass@acct/DB/PUBLIC?authenticator=some_unknown_auth"
        )

    # Rejected unsafe URLs (SSRF protection)
    with pytest.raises(ValueError, match="unsupported Snowflake authenticator URL"):
        await _parse_snowflake_dsn(
            "snowflake://user:pass@acct/DB/PUBLIC?authenticator=https://127.0.0.1:8000"
        )
    with pytest.raises(ValueError, match="unsupported Snowflake authenticator URL"):
        await _parse_snowflake_dsn(
            "snowflake://user:pass@acct/DB/PUBLIC?authenticator=https://evil.com"
        )


@pytest.mark.asyncio
async def test_introspect_snowflake_builds_common_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_kwargs: dict[str, Any] = {}

    def fake_connect(**kwargs: str) -> FakeConnection:
        captured_kwargs.update(kwargs)
        return FakeConnection()

    async def fake_validated_ip_hosts(host, is_hostaddr, port):
        return (host,)

    monkeypatch.setattr("app.snowflake_introspect.introspect._connect", fake_connect)
    monkeypatch.setattr(
        "app.snowflake_introspect.introspect._validated_ip_hosts",
        fake_validated_ip_hosts,
    )

    snapshot = await introspect_snowflake(
        "snowflake://user:pass@acct/APP_DB/PUBLIC?warehouse=COMPUTE_WH&role=ANALYST",
        None,
    )

    assert captured_kwargs == {
        "account": "acct",
        "user": "user",
        "password": "pass",
        "database": "APP_DB",
        "schema": "PUBLIC",
        "warehouse": "COMPUTE_WH",
        "role": "ANALYST",
    }
    assert snapshot["source_dialect"] == "snowflake"
    assert snapshot["database_name"] == "APP_DB"
    assert snapshot["schema_filter"] == "PUBLIC"
    assert snapshot["server_version"] == "8.30.1"
    assert snapshot["schemas"] == [{"schema_oid": 1, "schema_name": "PUBLIC"}]

    relations = snapshot["relations"]
    assert [row["relation_name"] for row in relations] == ["CUSTOMERS", "ORDERS"]
    assert relations[0]["relation_oid"] == 1
    assert relations[1]["relation_oid"] == 2

    columns = snapshot["columns"]
    assert columns[0]["data_type"] == "NUMBER(38,0)"
    assert columns[1]["data_type"] == "VARCHAR(100)"
    assert columns[4]["data_type"] == "TIMESTAMP_NTZ(9)"
    assert columns[1]["example_value"] == "user@example.com"

    constraints = snapshot["constraints"]
    fk = next(
        row for row in constraints if row["constraint_name"] == "ORDERS_CUSTOMER_FK"
    )
    assert fk["constraint_type"] == "f"
    assert fk["relation_oid"] == 2
    assert fk["foreign_relation_oid"] == 1
    assert (
        fk["constraint_def"]
        == 'FOREIGN KEY ("CUSTOMER_ID") REFERENCES "PUBLIC"."CUSTOMERS" ("CUSTOMER_ID")'
    )
    assert snapshot["pk_columns"][0]["column_name"] == "CUSTOMER_ID"
    assert snapshot["fk_edges"][0]["parent_relation_name"] == "CUSTOMERS"
