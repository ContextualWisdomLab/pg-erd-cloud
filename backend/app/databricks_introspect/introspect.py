"""Read-only Databricks SQL introspection through Unity Catalog.

This module deliberately exposes no SQL-apply surface. It accepts a strict DSN,
validates the workspace hostname against the shared SSRF guard, and executes a
fixed set of ``information_schema`` queries. Unity Catalog is mandatory because
the constraint relations used here are not available in the legacy metastore.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import importlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, unquote, urlparse

from app.pg_introspect.column_examples import add_column_examples
from app.pg_introspect.dsn_guard import _validated_ip_hosts
from app.sanitize import sanitize_for_storage

VERSION_SQL = """
SELECT coalesce(
  current_version().dbsql_version,
  current_version().dbr_version,
  version()
) AS server_version
"""

SCHEMAS_SQL = """
SELECT schema_name
FROM information_schema.schemata
WHERE catalog_name = current_catalog()
  AND schema_name <> 'information_schema'
  AND (? IS NULL OR schema_name = ?)
ORDER BY schema_name
"""

TABLES_SQL = """
SELECT table_schema, table_name, table_type, comment
FROM information_schema.tables
WHERE table_catalog = current_catalog()
  AND table_schema <> 'information_schema'
  AND (? IS NULL OR table_schema = ?)
ORDER BY table_schema, table_name
"""

COLUMNS_SQL = """
SELECT
  table_schema,
  table_name,
  ordinal_position,
  column_name,
  full_data_type,
  is_nullable,
  column_default,
  comment
FROM information_schema.columns
WHERE table_catalog = current_catalog()
  AND table_schema <> 'information_schema'
  AND (? IS NULL OR table_schema = ?)
ORDER BY table_schema, table_name, ordinal_position
"""

CONSTRAINT_COLUMNS_SQL = """
SELECT
  tc.constraint_schema,
  tc.constraint_name,
  tc.constraint_type,
  tc.enforced,
  tc.is_deferrable,
  tc.initially_deferred,
  tc.table_schema,
  tc.table_name,
  kcu.column_name,
  kcu.ordinal_position,
  pk_kcu.table_schema AS referenced_table_schema,
  pk_kcu.table_name AS referenced_table_name,
  pk_kcu.column_name AS referenced_column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON kcu.constraint_catalog = tc.constraint_catalog
  AND kcu.constraint_schema = tc.constraint_schema
  AND kcu.constraint_name = tc.constraint_name
LEFT JOIN information_schema.referential_constraints rc
  ON rc.constraint_catalog = tc.constraint_catalog
  AND rc.constraint_schema = tc.constraint_schema
  AND rc.constraint_name = tc.constraint_name
LEFT JOIN information_schema.key_column_usage pk_kcu
  ON pk_kcu.constraint_catalog = rc.unique_constraint_catalog
  AND pk_kcu.constraint_schema = rc.unique_constraint_schema
  AND pk_kcu.constraint_name = rc.unique_constraint_name
  AND pk_kcu.ordinal_position = kcu.position_in_unique_constraint
WHERE tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE', 'FOREIGN KEY')
  AND tc.table_catalog = current_catalog()
  AND (? IS NULL OR tc.table_schema = ?)
ORDER BY tc.table_schema, tc.table_name, tc.constraint_name, kcu.ordinal_position
"""

_SUPPORTED_QUERY_PARAMS = {"catalog", "schema"}


@dataclass(frozen=True)
class DatabricksDsnConfig:
    """Validated connection settings for the Databricks SQL connector."""

    server_hostname: str
    http_path: str
    access_token: str
    catalog: str
    schema: str | None

    def connect_kwargs(self) -> dict[str, object]:
        """Return the connector arguments without logging or serializing secrets."""
        kwargs = {
            "server_hostname": self.server_hostname,
            "http_path": self.http_path,
            "access_token": self.access_token,
            "catalog": self.catalog,
            # Metadata result sets are bounded and must not introduce a second
            # cloud-object-store egress path.
            "use_cloud_fetch": False,
        }
        if self.schema:
            kwargs["schema"] = self.schema
        return kwargs


async def _parse_databricks_dsn(dsn: str) -> DatabricksDsnConfig:
    parsed = urlparse(dsn)
    scheme = parsed.scheme.lower().split("+", 1)[0]
    if scheme != "databricks":
        raise ValueError("Databricks DSN must use the databricks scheme")
    if not parsed.hostname:
        raise ValueError("Databricks DSN must include a workspace hostname")
    if unquote(parsed.username or "") != "token":
        raise ValueError("Databricks DSN username must be token")
    if parsed.port not in (None, 443):
        raise ValueError("Databricks DSN only permits HTTPS port 443")
    if not parsed.password:
        raise ValueError("Databricks DSN must include an access token as the password")

    http_path = unquote(parsed.path)
    if not http_path.startswith("/sql/1.0/warehouses/"):
        raise ValueError(
            "Databricks DSN path must identify a SQL warehouse under "
            "/sql/1.0/warehouses/"
        )
    if http_path.endswith("/") or len(http_path.split("/")) != 5:
        raise ValueError("Databricks DSN must identify exactly one SQL warehouse")

    query: dict[str, str] = {}
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        normalized = key.lower()
        if normalized not in _SUPPORTED_QUERY_PARAMS:
            raise ValueError(f"unsupported Databricks DSN query parameter: {key}")
        if normalized in query:
            raise ValueError(f"duplicate Databricks DSN query parameter: {key}")
        if not value:
            raise ValueError(f"Databricks DSN query parameter is blank: {key}")
        query[normalized] = value
    catalog = query.get("catalog")
    if not catalog:
        raise ValueError("Databricks DSN must include a catalog query parameter")

    await _validated_ip_hosts(parsed.hostname, is_hostaddr=False, port=443)
    return DatabricksDsnConfig(
        server_hostname=parsed.hostname,
        http_path=http_path,
        access_token=unquote(parsed.password),
        catalog=catalog,
        schema=query.get("schema"),
    )


def _connect(**kwargs: object) -> Any:
    try:
        connector = importlib.import_module("databricks.sql")
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "Databricks reverse engineering requires the optional "
            "databricks-sql-connector package"
        ) from exc
    return connector.connect(**kwargs)


def _fetch_dicts(
    cursor: Any, sql: str, params: tuple[object, ...] = ()
) -> list[dict[str, object]]:
    cursor.execute(sql, params or None)
    rows = cursor.fetchall()
    if not rows:
        return []
    names = [str(description[0]).lower() for description in cursor.description or []]
    if isinstance(rows[0], dict):
        return [
            {str(key).lower(): value for key, value in row.items()} for row in rows
        ]
    return [dict(zip(names, row)) for row in rows]


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _int_or_zero(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _relation_kind(table_type: object) -> str:
    normalized = str(table_type or "").upper()
    if normalized == "VIEW":
        return "v"
    if normalized == "MATERIALIZED_VIEW":
        return "m"
    return "r"


def _quote(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'


def _constraint_type(value: object) -> str | None:
    return {
        "PRIMARY KEY": "p",
        "UNIQUE": "u",
        "FOREIGN KEY": "f",
    }.get(str(value or "").upper())


def _build_snapshot(
    config: DatabricksDsnConfig,
    effective_schema: str | None,
    version_rows: list[dict[str, object]],
    schema_rows: list[dict[str, object]],
    table_rows: list[dict[str, object]],
    column_rows: list[dict[str, object]],
    constraint_rows: list[dict[str, object]],
) -> dict[str, object]:
    relation_keys = sorted(
        {
            (str(row.get("table_schema") or ""), str(row.get("table_name") or ""))
            for row in table_rows
            if row.get("table_schema") and row.get("table_name")
        }
    )
    relation_ids = {key: index for index, key in enumerate(relation_keys, start=1)}
    table_by_key = {
        (str(row.get("table_schema") or ""), str(row.get("table_name") or "")): row
        for row in table_rows
    }

    schemas = [
        {"schema_oid": index, "schema_name": str(row["schema_name"])}
        for index, row in enumerate(schema_rows, start=1)
        if isinstance(row.get("schema_name"), str)
    ]
    relations: list[dict[str, object]] = []
    for schema, table in relation_keys:
        row = table_by_key[(schema, table)]
        relations.append(
            {
                "schema_name": schema,
                "relation_oid": relation_ids[(schema, table)],
                "relation_name": table,
                "relation_kind": _relation_kind(row.get("table_type")),
                "relation_comment": row.get("comment"),
                "is_partition": False,
                "partition_key": None,
                "partition_bound": None,
                "partition_parent_oid": None,
                "partition_parent_schema": None,
                "partition_parent_name": None,
                "tablespace_name": None,
            }
        )

    positions: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)
    columns: list[dict[str, object]] = []
    for row in column_rows:
        key = (str(row.get("table_schema") or ""), str(row.get("table_name") or ""))
        relation_oid = relation_ids.get(key)
        name = _text(row.get("column_name"))
        position = _int_or_zero(row.get("ordinal_position"))
        if relation_oid is None or not name or position < 1:
            continue
        positions[key][name] = position
        data_type = str(row.get("full_data_type") or "")
        columns.append(
            {
                "schema_name": key[0],
                "relation_oid": relation_oid,
                "relation_name": key[1],
                "relation_kind": _relation_kind(table_by_key[key].get("table_type")),
                "column_position": position,
                "column_name": name,
                "data_type": data_type,
                "type_oid": None,
                "type_schema": "information_schema",
                "type_name": data_type,
                "type_kind": None,
                "type_category": None,
                "domain_base_type": None,
                "domain_base_schema": None,
                "domain_base_name": None,
                "array_element_type": None,
                "array_element_schema": None,
                "array_element_name": None,
                "array_dimensions": 0,
                "is_not_null": str(row.get("is_nullable") or "").upper() == "NO",
                "has_default": row.get("column_default") is not None,
                "default_expr": row.get("column_default"),
                "column_comment": row.get("comment"),
            }
        )

    grouped: dict[tuple[str, str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in constraint_rows:
        schema_name = _text(row.get("table_schema"))
        table_name = _text(row.get("table_name"))
        name = _text(row.get("constraint_name"))
        kind = _constraint_type(row.get("constraint_type"))
        constraint_schema = _text(row.get("constraint_schema")) or schema_name
        if schema_name and table_name and name and kind and constraint_schema:
            grouped[(constraint_schema, name, schema_name, table_name)].append(row)

    constraints: list[dict[str, object]] = []
    pk_columns: list[dict[str, object]] = []
    fk_edges: list[dict[str, object]] = []
    for (_, name, schema, table), rows in sorted(grouped.items()):
        relation_oid = relation_ids.get((schema, table))
        if relation_oid is None:
            continue
        ordered = sorted(rows, key=lambda row: _int_or_zero(row.get("ordinal_position")))
        kind = _constraint_type(ordered[0].get("constraint_type"))
        names = [
            column
            for row in ordered
            if (column := _text(row.get("column_name"))) is not None
        ]
        attnums = [positions[(schema, table)][column] for column in names]
        constraint_oid = len(constraints) + 1
        referenced_schema = _text(ordered[0].get("referenced_table_schema"))
        referenced_table = _text(ordered[0].get("referenced_table_name"))
        referenced_names = [
            column
            for row in ordered
            if (column := _text(row.get("referenced_column_name"))) is not None
        ]
        foreign_oid = (
            relation_ids.get((referenced_schema, referenced_table))
            if referenced_schema and referenced_table
            else None
        )
        quoted = ", ".join(_quote(column) for column in names)
        if kind == "p":
            definition = f"PRIMARY KEY ({quoted})"
        elif kind == "u":
            definition = f"UNIQUE ({quoted})"
        else:
            referenced = ", ".join(_quote(column) for column in referenced_names)
            definition = f"FOREIGN KEY ({quoted})"
            if referenced_schema and referenced_table and referenced_names:
                definition += (
                    f" REFERENCES {_quote(referenced_schema)}.{_quote(referenced_table)}"
                    f" ({referenced})"
                )
        constraints.append(
            {
                "constraint_oid": constraint_oid,
                "constraint_name": name,
                "constraint_type": kind,
                "schema_name": schema,
                "relation_oid": relation_oid,
                "relation_name": table,
                "foreign_relation_oid": foreign_oid,
                "foreign_schema_name": referenced_schema,
                "foreign_relation_name": referenced_table,
                "constrained_attnums": attnums,
                "referenced_attnums": [],
                "constraint_def": definition,
                "check_expr": None,
                "constraint_enforced": str(ordered[0].get("enforced") or "NO").upper()
                == "YES",
                "constraint_deferrable": str(
                    ordered[0].get("is_deferrable") or "YES"
                ).upper()
                == "YES",
                "constraint_initially_deferred": str(
                    ordered[0].get("initially_deferred") or "NO"
                ).upper()
                == "YES",
            }
        )
        if kind == "p":
            for ordinal, column in enumerate(names, start=1):
                pk_columns.append(
                    {
                        "constraint_oid": constraint_oid,
                        "constraint_name": name,
                        "schema_name": schema,
                        "relation_oid": relation_oid,
                        "relation_name": table,
                        "column_ordinal": ordinal,
                        "column_name": column,
                    }
                )
        if kind == "f" and referenced_schema and referenced_table:
            for ordinal, row in enumerate(ordered, start=1):
                child = _text(row.get("column_name"))
                parent = _text(row.get("referenced_column_name"))
                if not child or not parent:
                    continue
                fk_edges.append(
                    {
                        "fk_constraint_oid": constraint_oid,
                        "fk_constraint_name": name,
                        "child_schema_name": schema,
                        "child_relation_oid": relation_oid,
                        "child_relation_name": table,
                        "parent_schema_name": referenced_schema,
                        "parent_relation_oid": foreign_oid,
                        "parent_relation_name": referenced_table,
                        "column_ordinal": ordinal,
                        "child_column_name": child,
                        "parent_column_name": parent,
                        "fk_on_update": "NO ACTION",
                        "fk_on_delete": "NO ACTION",
                        "fk_match_type": None,
                    }
                )

    server_version = (
        str(version_rows[0].get("server_version"))
        if version_rows and version_rows[0].get("server_version") is not None
        else "databricks"
    )
    snapshot: dict[str, object] = {
        "source_dialect": "databricks",
        "database_dialect": "databricks",
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "server_version": server_version,
        "database_name": config.catalog,
        "schema_filter": effective_schema,
        "schemas": schemas,
        "relations": relations,
        "columns": add_column_examples(columns),
        "constraints": constraints,
        "indexes": [],
        "pk_columns": pk_columns,
        "fk_edges": fk_edges,
        "introspection_capabilities": {
            "unity_catalog": "required",
            "tables": "implemented",
            "columns": "implemented",
            "primary_unique_foreign_keys": "preview",
            "constraint_enforcement": "reported_per_constraint",
            "indexes": "unsupported",
            "check_constraints": "unsupported",
        },
    }
    return sanitize_for_storage(snapshot)  # type: ignore[return-value]


def _introspect_sync(
    config: DatabricksDsnConfig, schema_filter: str | None
) -> dict[str, object]:
    effective_schema = schema_filter or config.schema
    params = (effective_schema, effective_schema)
    conn = _connect(**config.connect_kwargs())
    cursor = conn.cursor()
    try:
        version_rows = _fetch_dicts(cursor, VERSION_SQL)
        schema_rows = _fetch_dicts(cursor, SCHEMAS_SQL, params)
        table_rows = _fetch_dicts(cursor, TABLES_SQL, params)
        column_rows = _fetch_dicts(cursor, COLUMNS_SQL, params)
        constraint_rows = _fetch_dicts(cursor, CONSTRAINT_COLUMNS_SQL, params)
    finally:
        try:
            cursor.close()
        finally:
            conn.close()
    return _build_snapshot(
        config,
        effective_schema,
        version_rows,
        schema_rows,
        table_rows,
        column_rows,
        constraint_rows,
    )


def _probe_sync(config: DatabricksDsnConfig) -> str:
    conn = _connect(**config.connect_kwargs())
    cursor = conn.cursor()
    try:
        rows = _fetch_dicts(cursor, VERSION_SQL)
        return str(rows[0].get("server_version") or "") if rows else ""
    finally:
        try:
            cursor.close()
        finally:
            conn.close()


async def introspect_databricks(
    dsn: str, schema_filter: str | None
) -> dict[str, object]:
    """Capture a Unity Catalog snapshot using only fixed read-only queries."""
    config = await _parse_databricks_dsn(dsn)
    return await asyncio.to_thread(_introspect_sync, config, schema_filter)


async def probe_databricks(dsn: str) -> str:
    """SSRF-guarded Databricks SQL connectivity probe."""
    config = await _parse_databricks_dsn(dsn)
    return await asyncio.to_thread(_probe_sync, config)
