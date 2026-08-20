from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

import app.databricks_introspect.introspect as databricks_introspect_module
from app.ddl.export import snapshot_json_to_sql
from app.ddl.migration import snapshot_diff_to_migration_sql


class FakeCursor:
    def __init__(self) -> None:
        self.description: list[tuple[str]] = []
        self._rows: list[tuple[object, ...]] = []
        self.closed = False

    def execute(self, sql: str, params: Sequence[object] | None = None) -> None:
        rows = _rows_for(sql, params or ())
        names = list(rows[0]) if rows else ["empty"]
        self.description = [(name,) for name in names]
        self._rows = [tuple(row.get(name) for name in names) for row in rows]

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


def _rows_for(sql: str, params: Sequence[object]) -> list[dict[str, object]]:
    if params:
        assert params[0] in (None, "sales")
    if "current_version" in sql:
        return [{"server_version": "17.3 LTS"}]
    if "information_schema.schemata" in sql:
        return [{"schema_name": "sales"}]
    if "information_schema.tables" in sql:
        return [
            {
                "table_schema": "sales",
                "table_name": "customers",
                "table_type": "MANAGED",
                "comment": "Customer master",
            },
            {
                "table_schema": "sales",
                "table_name": "orders",
                "table_type": "VIEW",
                "comment": None,
            },
        ]
    if "information_schema.columns" in sql:
        return [
            {
                "table_schema": "sales",
                "table_name": "customers",
                "ordinal_position": 1,
                "column_name": "customer_id",
                "full_data_type": "BIGINT",
                "is_nullable": "NO",
                "column_default": None,
                "comment": "Key",
            },
            {
                "table_schema": "sales",
                "table_name": "orders",
                "ordinal_position": 1,
                "column_name": "customer_id",
                "full_data_type": "BIGINT",
                "is_nullable": "YES",
                "column_default": None,
                "comment": None,
            },
        ]
    if "information_schema.table_constraints" in sql:
        return [
            {
                "constraint_schema": "sales",
                "constraint_name": "customers_pk",
                "constraint_type": "PRIMARY KEY",
                "enforced": "NO",
                "is_deferrable": "YES",
                "initially_deferred": "NO",
                "table_schema": "sales",
                "table_name": "customers",
                "column_name": "customer_id",
                "ordinal_position": 1,
                "referenced_table_schema": None,
                "referenced_table_name": None,
                "referenced_column_name": None,
            },
            {
                "constraint_schema": "sales",
                "constraint_name": "orders_customer_fk",
                "constraint_type": "FOREIGN KEY",
                "enforced": "NO",
                "is_deferrable": "YES",
                "initially_deferred": "NO",
                "table_schema": "sales",
                "table_name": "orders",
                "column_name": "customer_id",
                "ordinal_position": 1,
                "referenced_table_schema": "sales",
                "referenced_table_name": "customers",
                "referenced_column_name": "customer_id",
            },
        ]
    return []


@pytest.mark.asyncio
async def test_parse_databricks_dsn_is_strict_and_ssrf_guarded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    guarded: list[tuple[str, bool, int]] = []

    async def fake_guard(host: str, is_hostaddr: bool, port: int) -> tuple[str]:
        guarded.append((host, is_hostaddr, port))
        return ("203.0.113.10",)

    monkeypatch.setattr(
        "app.databricks_introspect.introspect._validated_ip_hosts", fake_guard
    )
    config = await databricks_introspect_module._parse_databricks_dsn(
        "databricks://token:s%2Fecret@workspace.cloud.databricks.com/"
        "sql/1.0/warehouses/abc?catalog=main&schema=sales"
    )

    assert config.server_hostname == "workspace.cloud.databricks.com"
    assert config.http_path == "/sql/1.0/warehouses/abc"
    assert config.access_token == "s/ecret"
    assert config.catalog == "main"
    assert config.schema == "sales"
    assert guarded == [("workspace.cloud.databricks.com", False, 443)]

    with pytest.raises(ValueError, match="provider-owned workspace hostname"):
        await databricks_introspect_module._parse_databricks_dsn(
            "databricks://token:secret@attacker.example/"
            "sql/1.0/warehouses/abc?catalog=main"
        )
    assert guarded == [("workspace.cloud.databricks.com", False, 443)]

    with pytest.raises(ValueError, match="unsupported Databricks DSN query parameter"):
        await databricks_introspect_module._parse_databricks_dsn(
            "databricks://token:secret@workspace.cloud.databricks.com/"
            "sql/1.0/warehouses/abc?catalog=main&http_path=/evil"
        )
    with pytest.raises(ValueError, match="must include an access token"):
        await databricks_introspect_module._parse_databricks_dsn(
            "databricks://token@workspace.cloud.databricks.com/"
            "sql/1.0/warehouses/abc?catalog=main"
        )


@pytest.mark.asyncio
async def test_introspect_databricks_builds_bounded_common_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_guard(host: str, is_hostaddr: bool, port: int) -> tuple[str]:
        return ("203.0.113.10",)

    def fake_connect(**kwargs: object) -> FakeConnection:
        captured.update(kwargs)
        return FakeConnection()

    monkeypatch.setattr(
        "app.databricks_introspect.introspect._validated_ip_hosts", fake_guard
    )
    monkeypatch.setattr("app.databricks_introspect.introspect._connect", fake_connect)

    snapshot = await databricks_introspect_module.introspect_databricks(
        "databricks://token:secret@workspace.cloud.databricks.com/"
        "sql/1.0/warehouses/abc?catalog=main&schema=sales",
        None,
    )

    assert captured == {
        "server_hostname": "workspace.cloud.databricks.com",
        "http_path": "/sql/1.0/warehouses/abc",
        "access_token": "secret",
        "catalog": "main",
        "schema": "sales",
        "use_cloud_fetch": False,
    }
    assert snapshot["source_dialect"] == "databricks"
    assert snapshot["database_name"] == "main"
    assert snapshot["schema_filter"] == "sales"
    assert snapshot["server_version"] == "17.3 LTS"
    assert snapshot["schemas"] == [{"schema_oid": 1, "schema_name": "sales"}]
    assert [row["relation_kind"] for row in snapshot["relations"]] == ["r", "v"]
    assert snapshot["columns"][0]["data_type"] == "BIGINT"
    assert snapshot["constraints"][0]["constraint_type"] == "p"
    assert snapshot["constraints"][0]["constraint_enforced"] is False
    assert snapshot["fk_edges"][0]["parent_relation_name"] == "customers"
    assert snapshot["introspection_capabilities"] == {
        "unity_catalog": "required",
        "tables": "implemented",
        "columns": "implemented",
        "primary_unique_foreign_keys": "preview",
        "constraint_enforcement": "reported_per_constraint",
        "indexes": "unsupported",
        "check_constraints": "unsupported",
    }


@pytest.mark.parametrize(
    "dialect_key", ["source_dialect", "database_dialect", "dialect"]
)
def test_databricks_snapshot_ddl_and_migration_fail_closed(
    dialect_key: str,
) -> None:
    snapshot = {
        dialect_key: "databricks",
        "relations": [],
        "columns": [],
        "constraints": [],
    }

    with pytest.raises(ValueError, match="Databricks snapshot DDL export"):
        snapshot_json_to_sql(snapshot)
    with pytest.raises(ValueError, match="Databricks snapshot migration"):
        snapshot_diff_to_migration_sql({}, snapshot)
    with pytest.raises(ValueError, match="Databricks snapshot migration"):
        snapshot_diff_to_migration_sql(snapshot, {})


def test_snapshot_skips_constraints_with_unknown_columns_and_defaults_flags() -> None:
    snapshot = databricks_introspect_module._build_snapshot(
        databricks_introspect_module.DatabricksDsnConfig(
            server_hostname="workspace.cloud.databricks.com",
            http_path="/sql/1.0/warehouses/abc",
            access_token="secret",  # noqa: S106 - inert unit-test fixture
            catalog="main",
            schema="sales",
        ),
        "sales",
        [],
        [{"schema_name": "sales"}],
        [
            {
                "table_schema": "sales",
                "table_name": "customers",
                "table_type": "MANAGED",
            }
        ],
        [
            {
                "table_schema": "sales",
                "table_name": "customers",
                "ordinal_position": 1,
                "column_name": "customer_id",
                "full_data_type": "BIGINT",
                "is_nullable": "NO",
            }
        ],
        [
            {
                "constraint_schema": "sales",
                "constraint_name": "customers_missing_pk",
                "constraint_type": "PRIMARY KEY",
                "table_schema": "sales",
                "table_name": "customers",
                "column_name": "customer_id",
                "ordinal_position": 1,
            },
            {
                "constraint_schema": "sales",
                "constraint_name": "customers_missing_pk",
                "constraint_type": "PRIMARY KEY",
                "table_schema": "sales",
                "table_name": "customers",
                "column_name": "privilege_filtered_column",
                "ordinal_position": 2,
            },
            {
                "constraint_schema": "sales",
                "constraint_name": "customers_unique",
                "constraint_type": "UNIQUE",
                "table_schema": "sales",
                "table_name": "customers",
                "column_name": "customer_id",
                "ordinal_position": 1,
            },
        ],
    )

    assert [row["constraint_name"] for row in snapshot["constraints"]] == [
        "customers_unique"
    ]
    assert snapshot["constraints"][0]["constraint_deferrable"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dsn,error",
    [
        ("postgresql://u:p@host/db", "must use the databricks scheme"),
        ("databricks:///sql/1.0/warehouses/abc?catalog=main", "workspace hostname"),
        (
            "databricks://user:x@host/sql/1.0/warehouses/abc?catalog=main",
            "username must be token",
        ),
        (
            "databricks://token:x@host:444/sql/1.0/warehouses/abc?catalog=main",
            "port 443",
        ),
        ("databricks://token:x@host/clusters/abc?catalog=main", "warehouse under"),
        (
            "databricks://token:x@host/sql/1.0/warehouses/abc/extra?catalog=main",
            "exactly one SQL warehouse",
        ),
        (
            "databricks://token:x@host/sql/1.0/warehouses/abc?catalog=main&catalog=two",
            "duplicate Databricks",
        ),
        (
            "databricks://token:x@host/sql/1.0/warehouses/abc?catalog=",
            "query parameter is blank",
        ),
        (
            "databricks://token:x@host/sql/1.0/warehouses/abc?schema=default",
            "must include a catalog",
        ),
    ],
)
async def test_parse_databricks_dsn_rejects_unsafe_or_ambiguous_inputs(
    dsn: str, error: str
) -> None:
    with pytest.raises(ValueError, match=error):
        await databricks_introspect_module._parse_databricks_dsn(dsn)


def test_optional_connector_failure_and_row_shapes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_connector(name: str) -> Any:
        raise ImportError(name)

    monkeypatch.setattr(
        databricks_introspect_module.importlib, "import_module", missing_connector
    )
    with pytest.raises(RuntimeError, match="databricks-sql-connector"):
        databricks_introspect_module._connect(server_hostname="workspace")

    class Connector:
        @staticmethod
        def connect(**kwargs: object) -> dict[str, object]:
            return kwargs

    monkeypatch.setattr(
        databricks_introspect_module.importlib,
        "import_module",
        lambda name: Connector,
    )
    assert databricks_introspect_module._connect(server_hostname="workspace") == {
        "server_hostname": "workspace"
    }

    class DictCursor:
        description = [("MixedCase",)]

        def __init__(self, rows: list[dict[str, object]]) -> None:
            self.rows = rows

        def execute(self, sql: str, params: object) -> None:
            assert sql == "fixed"
            assert params is None

        def fetchall(self) -> list[dict[str, object]]:
            return self.rows

    assert databricks_introspect_module._fetch_dicts(DictCursor([]), "fixed") == []
    assert databricks_introspect_module._fetch_dicts(
        DictCursor([{"MixedCase": 1}]), "fixed"
    ) == [
        {"mixedcase": 1}
    ]

    class MismatchedTupleCursor:
        description = (("one",), ("two",))

        def execute(self, sql: str, params: object) -> None:
            assert sql == "fixed"
            assert params is None

        def fetchall(self) -> list[tuple[object, ...]]:
            return [(1,)]

    with pytest.raises(ValueError, match=r"zip\(\) argument 2 is shorter"):
        databricks_introspect_module._fetch_dicts(MismatchedTupleCursor(), "fixed")


@pytest.mark.asyncio
async def test_probe_databricks_returns_version_and_closes_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = FakeConnection()

    async def fake_guard(host: str, is_hostaddr: bool, port: int) -> tuple[str]:
        return ("203.0.113.10",)

    monkeypatch.setattr(
        "app.databricks_introspect.introspect._validated_ip_hosts", fake_guard
    )
    monkeypatch.setattr(
        "app.databricks_introspect.introspect._connect", lambda **kwargs: connection
    )

    version = await databricks_introspect_module.probe_databricks(
        "databricks://token:secret@workspace.cloud.databricks.com/"
        "sql/1.0/warehouses/abc?catalog=main"
    )

    assert version == "17.3 LTS"
    assert connection.cursor_instance.closed is True
    assert connection.closed is True


def test_snapshot_builder_covers_unique_materialized_and_malformed_rows() -> None:
    config = databricks_introspect_module.DatabricksDsnConfig(
        server_hostname="workspace",
        http_path="/sql/1.0/warehouses/abc",
        access_token="secret",
        catalog="main",
        schema=None,
    )
    snapshot = databricks_introspect_module._build_snapshot(
        config,
        None,
        [],
        [{"schema_name": "s"}],
        [
            {
                "table_schema": "s",
                "table_name": "mv",
                "table_type": "MATERIALIZED_VIEW",
            }
        ],
        [
            {
                "table_schema": "missing",
                "table_name": "table",
                "ordinal_position": "bad",
                "column_name": "ignored",
            },
            {
                "table_schema": "s",
                "table_name": "mv",
                "ordinal_position": "1",
                "column_name": "id",
                "full_data_type": "BIGINT",
            },
        ],
        [
            {
                "constraint_schema": "s",
                "constraint_name": "mv_id_unique",
                "constraint_type": "UNIQUE",
                "table_schema": "s",
                "table_name": "mv",
                "column_name": "id",
                "ordinal_position": "1",
            },
            {
                "constraint_schema": "missing",
                "constraint_name": "not_visible",
                "constraint_type": "PRIMARY KEY",
                "table_schema": "missing",
                "table_name": "table",
                "column_name": "id",
                "ordinal_position": 1,
            },
            {
                "constraint_schema": "s",
                "constraint_name": "broken_fk",
                "constraint_type": "FOREIGN KEY",
                "table_schema": "s",
                "table_name": "mv",
                "column_name": "id",
                "ordinal_position": 1,
                "referenced_table_schema": "s",
                "referenced_table_name": "mv",
                "referenced_column_name": None,
            },
            {"constraint_type": "CHECK"},
        ],
    )

    assert snapshot["server_version"] == "databricks"
    assert snapshot["relations"][0]["relation_kind"] == "m"
    assert any(
        row["constraint_def"] == 'UNIQUE ("id")'
        for row in snapshot["constraints"]
    )
