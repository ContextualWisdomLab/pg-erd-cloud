from __future__ import annotations

import asyncio
import datetime as dt
import importlib
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, unquote, urlparse

from app.pg_introspect.column_examples import add_column_examples
from app.sanitize import sanitize_for_storage

SCHEMAS_SQL = """
SELECT schema_name
FROM information_schema.schemata
WHERE catalog_name = CURRENT_DATABASE()
  AND schema_name <> 'INFORMATION_SCHEMA'
  AND (%s IS NULL OR schema_name = %s)
ORDER BY schema_name
"""

TABLES_SQL = """
SELECT table_schema, table_name, table_type, comment
FROM information_schema.tables
WHERE table_schema <> 'INFORMATION_SCHEMA'
  AND (%s IS NULL OR table_schema = %s)
ORDER BY table_schema, table_name
"""

COLUMNS_SQL = """
SELECT
  table_schema,
  table_name,
  ordinal_position,
  column_name,
  data_type,
  character_maximum_length,
  numeric_precision,
  numeric_scale,
  datetime_precision,
  is_nullable,
  column_default,
  comment
FROM information_schema.columns
WHERE table_schema <> 'INFORMATION_SCHEMA'
  AND (%s IS NULL OR table_schema = %s)
ORDER BY table_schema, table_name, ordinal_position
"""

CONSTRAINT_COLUMNS_SQL = """
SELECT
  tc.constraint_schema,
  tc.constraint_name,
  tc.constraint_type,
  tc.table_schema,
  tc.table_name,
  kcu.column_name,
  kcu.ordinal_position,
  pk_kcu.table_schema AS referenced_table_schema,
  pk_kcu.table_name AS referenced_table_name,
  pk_kcu.column_name AS referenced_column_name
FROM information_schema.table_constraints tc
LEFT JOIN information_schema.key_column_usage kcu
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
  AND (%s IS NULL OR tc.table_schema = %s)
ORDER BY
  tc.table_schema,
  tc.table_name,
  tc.constraint_name,
  kcu.ordinal_position
"""

VERSION_SQL = "SELECT CURRENT_VERSION() AS server_version"

SUPPORTED_QUERY_PARAMS = {"warehouse", "role", "authenticator"}


@dataclass(frozen=True)
class SnowflakeDsnConfig:
    account: str
    user: str
    password: str | None
    database: str
    schema: str | None
    warehouse: str | None
    role: str | None
    authenticator: str | None

    def connect_kwargs(self) -> dict[str, str]:
        kwargs = {
            "account": self.account,
            "user": self.user,
            "database": self.database,
        }
        optional = {
            "password": self.password,
            "schema": self.schema,
            "warehouse": self.warehouse,
            "role": self.role,
            "authenticator": self.authenticator,
        }
        for key, value in optional.items():
            if value:
                kwargs[key] = value
        return kwargs


def _int_or_none(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _parse_snowflake_dsn(dsn: str) -> SnowflakeDsnConfig:
    parsed = urlparse(dsn)
    if parsed.scheme.lower() != "snowflake":
        raise ValueError("Snowflake DSN must use the snowflake scheme")
    if not parsed.hostname:
        raise ValueError("Snowflake DSN must include an account identifier")
    if not parsed.username:
        raise ValueError("Snowflake DSN must include a user")

    path_parts = [unquote(part) for part in parsed.path.split("/") if part]
    if not path_parts:
        raise ValueError("Snowflake DSN must include a database path segment")
    if len(path_parts) > 2:
        raise ValueError("Snowflake DSN path must be /database or /database/schema")

    query: dict[str, str] = {}
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        normalized = key.lower()
        if normalized not in SUPPORTED_QUERY_PARAMS:
            raise ValueError(f"unsupported Snowflake DSN query parameter: {key}")
        if not value:
            raise ValueError(f"Snowflake DSN query parameter is blank: {key}")

        if normalized == "authenticator":
            # Prevent SSRF: only allow known safe authenticator values or Okta URLs
            auth_lower = value.lower()
            safe_auths = {
                "snowflake",
                "snowflake_jwt",
                "externalbrowser",
                "oauth",
                "username_password_mfa",
            }
            if auth_lower not in safe_auths:
                if not auth_lower.startswith("https://"):
                    raise ValueError("unsupported Snowflake authenticator value")
                parsed_auth = urlparse(auth_lower)
                if (
                    not parsed_auth.hostname
                    or not re.match(r"^[a-zA-Z0-9.-]+$", parsed_auth.hostname)
                    or not (
                        parsed_auth.hostname == "okta.com" or parsed_auth.hostname.endswith(".okta.com") or
                        parsed_auth.hostname == "oktapreview.com" or parsed_auth.hostname.endswith(".oktapreview.com")
                    )
                    or parsed_auth.username
                    or parsed_auth.password
                    or parsed_auth.query
                    or parsed_auth.fragment
                    or (parsed_auth.path and parsed_auth.path not in ("", "/"))
                ):
                    raise ValueError("unsupported Snowflake authenticator URL")

        query[normalized] = value

    return SnowflakeDsnConfig(
        account=parsed.hostname,
        user=unquote(parsed.username),
        password=unquote(parsed.password) if parsed.password else None,
        database=path_parts[0],
        schema=path_parts[1] if len(path_parts) == 2 else None,
        warehouse=query.get("warehouse"),
        role=query.get("role"),
        authenticator=query.get("authenticator"),
    )


def _connect(**kwargs: str) -> Any:
    try:
        connector = importlib.import_module("snowflake.connector")
    except ImportError as exc:
        raise RuntimeError(
            "Snowflake reverse engineering requires the optional "
            "snowflake-connector-python package"
        ) from exc
    return connector.connect(**kwargs)


def _fetch_dicts(cursor: Any, sql: str, params: tuple[object, ...] = ()) -> list[dict]:
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    if not rows:
        return []
    if isinstance(rows[0], dict):
        return [{str(key).lower(): value for key, value in row.items()} for row in rows]

    columns = [str(description[0]).lower() for description in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def _snowflake_relation_kind(table_type: object) -> str:
    normalized = str(table_type or "").upper()
    if "VIEW" in normalized:
        return "m" if "MATERIALIZED" in normalized else "v"
    return "r"


def _format_snowflake_data_type(row: dict) -> str:
    data_type = str(row.get("data_type") or "VARCHAR").upper()
    precision = _int_or_none(row.get("numeric_precision"))
    scale = _int_or_none(row.get("numeric_scale"))
    char_length = _int_or_none(row.get("character_maximum_length"))
    datetime_precision = _int_or_none(row.get("datetime_precision"))

    if data_type in ("NUMBER", "NUMERIC", "DECIMAL") and precision is not None:
        return f"{data_type}({precision},{scale or 0})"
    if data_type in ("VARCHAR", "CHAR", "CHARACTER", "STRING", "TEXT"):
        if char_length is not None and char_length > 0:
            return f"{data_type}({char_length})"
        return data_type
    if data_type.startswith("TIMESTAMP") and datetime_precision is not None:
        return f"{data_type}({datetime_precision})"
    return data_type


def _table_key(row: dict) -> tuple[str, str]:
    return (str(row.get("table_schema") or ""), str(row.get("table_name") or ""))


def _q(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'


def _constraint_type(value: object) -> str | None:
    normalized = str(value or "").upper()
    if normalized == "PRIMARY KEY":
        return "p"
    if normalized == "UNIQUE":
        return "u"
    if normalized == "FOREIGN KEY":
        return "f"
    return None


def _constraint_def(
    constraint_type: str,
    columns: list[str],
    referenced_schema: str | None,
    referenced_table: str | None,
    referenced_columns: list[str],
) -> str:
    quoted_cols = ", ".join(_q(col) for col in columns)
    if constraint_type == "p":
        return f"PRIMARY KEY ({quoted_cols})"
    if constraint_type == "u":
        return f"UNIQUE ({quoted_cols})"
    if referenced_schema and referenced_table and referenced_columns:
        quoted_ref_cols = ", ".join(_q(col) for col in referenced_columns)
        return (
            f"FOREIGN KEY ({quoted_cols}) REFERENCES "
            f"{_q(referenced_schema)}.{_q(referenced_table)} ({quoted_ref_cols})"
        )
    return f"FOREIGN KEY ({quoted_cols})"


def _build_primary_key(
    name: str,
    schema: str,
    table: str,
    relation_oid: int,
    columns: list[str],
    constrained_attnums: list[int],
    constraint_oid: int,
) -> tuple[dict, list[dict]]:
    constraint = {
        "constraint_oid": constraint_oid,
        "constraint_name": name,
        "constraint_type": "p",
        "schema_name": schema,
        "relation_oid": relation_oid,
        "relation_name": table,
        "foreign_relation_oid": None,
        "foreign_schema_name": None,
        "foreign_relation_name": None,
        "constrained_attnums": constrained_attnums,
        "referenced_attnums": [],
        "constraint_def": _constraint_def("p", columns, None, None, []),
        "check_expr": None,
    }

    pk_columns = []
    for ordinal, column in enumerate(columns, start=1):
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
    return constraint, pk_columns


def _build_unique_constraint(
    name: str,
    schema: str,
    table: str,
    relation_oid: int,
    columns: list[str],
    constrained_attnums: list[int],
    constraint_oid: int,
) -> dict:
    return {
        "constraint_oid": constraint_oid,
        "constraint_name": name,
        "constraint_type": "u",
        "schema_name": schema,
        "relation_oid": relation_oid,
        "relation_name": table,
        "foreign_relation_oid": None,
        "foreign_schema_name": None,
        "foreign_relation_name": None,
        "constrained_attnums": constrained_attnums,
        "referenced_attnums": [],
        "constraint_def": _constraint_def("u", columns, None, None, []),
        "check_expr": None,
    }


def _build_foreign_key(
    name: str,
    schema: str,
    table: str,
    relation_oid: int,
    columns: list[str],
    constrained_attnums: list[int],
    constraint_oid: int,
    referenced_schema: str | None,
    referenced_table: str | None,
    referenced_columns: list[str],
    foreign_relation_oid: int | None,
    sorted_rows: list[dict],
) -> tuple[dict, list[dict]]:
    constraint = {
        "constraint_oid": constraint_oid,
        "constraint_name": name,
        "constraint_type": "f",
        "schema_name": schema,
        "relation_oid": relation_oid,
        "relation_name": table,
        "foreign_relation_oid": foreign_relation_oid,
        "foreign_schema_name": referenced_schema,
        "foreign_relation_name": referenced_table,
        "constrained_attnums": constrained_attnums,
        "referenced_attnums": [],
        "constraint_def": _constraint_def(
            "f",
            columns,
            referenced_schema,
            referenced_table,
            referenced_columns,
        ),
        "check_expr": None,
    }

    fk_edges = []
    if referenced_schema and referenced_table:
        for ordinal, row in enumerate(sorted_rows, start=1):
            child_column = _str_or_none(row.get("column_name"))
            parent_column = _str_or_none(row.get("referenced_column_name"))
            if not (child_column and parent_column):
                continue
            fk_edges.append(
                {
                    "fk_constraint_oid": constraint_oid,
                    "fk_constraint_name": name,
                    "child_schema_name": schema,
                    "child_relation_oid": relation_oid,
                    "child_relation_name": table,
                    "parent_schema_name": referenced_schema,
                    "parent_relation_oid": foreign_relation_oid,
                    "parent_relation_name": referenced_table,
                    "column_ordinal": ordinal,
                    "child_column_name": child_column,
                    "parent_column_name": parent_column,
                    "fk_on_update": None,
                    "fk_on_delete": None,
                    "fk_match_type": None,
                }
            )

    return constraint, fk_edges


def _build_constraints(
    rows: list[dict],
    relation_ids: dict[tuple[str, str], int],
    column_positions: dict[tuple[str, str], dict[str, int]],
) -> tuple[list[dict], list[dict], list[dict]]:
    grouped: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        ctype = _constraint_type(row.get("constraint_type"))
        schema = _str_or_none(row.get("table_schema"))
        table = _str_or_none(row.get("table_name"))
        name = _str_or_none(row.get("constraint_name"))
        constraint_schema = _str_or_none(row.get("constraint_schema")) or schema
        if not (ctype and schema and table and name and constraint_schema):
            continue
        grouped[(constraint_schema, name, schema, table)].append(row)

    constraints: list[dict] = []
    pk_columns: list[dict] = []
    fk_edges: list[dict] = []

    for (_, name, schema, table), group_rows in grouped.items():
        sorted_rows = sorted(
            group_rows,
            key=lambda row: int(row.get("ordinal_position") or 0),
        )
        ctype = _constraint_type(sorted_rows[0].get("constraint_type"))
        if ctype is None:
            continue
        relation_oid = relation_ids.get((schema, table))
        if relation_oid is None:
            continue

        columns = [
            str(row["column_name"])
            for row in sorted_rows
            if isinstance(row.get("column_name"), str)
        ]
        attnums = [
            column_positions.get((schema, table), {}).get(column) for column in columns
        ]
        constrained_attnums = [attnum for attnum in attnums if isinstance(attnum, int)]
        referenced_schema = _str_or_none(sorted_rows[0].get("referenced_table_schema"))
        referenced_table = _str_or_none(sorted_rows[0].get("referenced_table_name"))
        referenced_columns = [
            str(row["referenced_column_name"])
            for row in sorted_rows
            if isinstance(row.get("referenced_column_name"), str)
        ]
        foreign_relation_oid = (
            relation_ids.get((referenced_schema, referenced_table))
            if referenced_schema and referenced_table
            else None
        )

        constraint_oid = len(constraints) + 1
        if ctype == "p":
            constraint, new_pk_columns = _build_primary_key(
                name,
                schema,
                table,
                relation_oid,
                columns,
                constrained_attnums,
                constraint_oid,
            )
            constraints.append(constraint)
            pk_columns.extend(new_pk_columns)
        elif ctype == "u":
            constraint = _build_unique_constraint(
                name,
                schema,
                table,
                relation_oid,
                columns,
                constrained_attnums,
                constraint_oid,
            )
            constraints.append(constraint)
        elif ctype == "f":
            constraint, new_fk_edges = _build_foreign_key(
                name,
                schema,
                table,
                relation_oid,
                columns,
                constrained_attnums,
                constraint_oid,
                referenced_schema,
                referenced_table,
                referenced_columns,
                foreign_relation_oid,
                sorted_rows,
            )
            constraints.append(constraint)
            fk_edges.extend(new_fk_edges)

    return constraints, pk_columns, fk_edges


def _build_snapshot(
    config: SnowflakeDsnConfig,
    effective_schema: str | None,
    version_rows: list[dict],
    schema_rows: list[dict],
    table_rows: list[dict],
    column_rows: list[dict],
    constraint_rows: list[dict],
) -> dict:
    relation_keys = sorted({_table_key(row) for row in table_rows})
    relation_ids = {key: index for index, key in enumerate(relation_keys, start=1)}
    column_positions: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)

    schemas = [
        {
            "schema_oid": index,
            "schema_name": str(row.get("schema_name")),
        }
        for index, row in enumerate(schema_rows, start=1)
        if isinstance(row.get("schema_name"), str)
    ]

    relations = []
    table_row_by_key = {_table_key(row): row for row in table_rows}
    for schema, table in relation_keys:
        row = table_row_by_key.get((schema, table), {})
        relations.append(
            {
                "schema_name": schema,
                "relation_oid": relation_ids[(schema, table)],
                "relation_name": table,
                "relation_kind": _snowflake_relation_kind(row.get("table_type")),
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

    columns = []
    for row in column_rows:
        schema, table = _table_key(row)
        relation_oid = relation_ids.get((schema, table))
        if relation_oid is None:
            continue
        column_name = _str_or_none(row.get("column_name"))
        position = _int_or_none(row.get("ordinal_position"))
        if not (column_name and position is not None):
            continue
        column_positions[(schema, table)][column_name] = position
        data_type = _format_snowflake_data_type(row)
        columns.append(
            {
                "schema_name": schema,
                "relation_oid": relation_oid,
                "relation_name": table,
                "relation_kind": "r",
                "column_position": position,
                "column_name": column_name,
                "data_type": data_type,
                "type_oid": None,
                "type_schema": "INFORMATION_SCHEMA",
                "type_name": str(row.get("data_type") or ""),
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

    constraints, pk_columns, fk_edges = _build_constraints(
        constraint_rows, relation_ids, column_positions
    )
    server_version = (
        str(version_rows[0].get("server_version"))
        if version_rows and version_rows[0].get("server_version") is not None
        else "snowflake"
    )
    snapshot = {
        "source_dialect": "snowflake",
        "database_dialect": "snowflake",
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "server_version": server_version,
        "database_name": config.database,
        "schema_filter": effective_schema,
        "schemas": schemas,
        "relations": relations,
        "columns": add_column_examples(columns),
        "constraints": constraints,
        "indexes": [],
        "pk_columns": pk_columns,
        "fk_edges": fk_edges,
    }
    return sanitize_for_storage(snapshot)  # type: ignore[return-value]


def _introspect_snowflake_sync(dsn: str, schema_filter: str | None) -> dict:
    config = _parse_snowflake_dsn(dsn)
    effective_schema = schema_filter or config.schema
    query_params = (effective_schema, effective_schema)

    conn = _connect(**config.connect_kwargs())
    cursor = conn.cursor()
    try:
        version_rows = _fetch_dicts(cursor, VERSION_SQL)
        schema_rows = _fetch_dicts(cursor, SCHEMAS_SQL, query_params)
        table_rows = _fetch_dicts(cursor, TABLES_SQL, query_params)
        column_rows = _fetch_dicts(cursor, COLUMNS_SQL, query_params)
        constraint_rows = _fetch_dicts(
            cursor, CONSTRAINT_COLUMNS_SQL, query_params
        )
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


async def introspect_snowflake(dsn: str, schema_filter: str | None) -> dict:
    """Introspect Snowflake metadata into the common snapshot JSON shape."""

    return await asyncio.to_thread(_introspect_snowflake_sync, dsn, schema_filter)
