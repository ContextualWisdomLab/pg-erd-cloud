"""MySQL / MariaDB introspection producing the common snapshot JSON.

Mirrors the Snowflake introspector's structure: SSRF-guarded DSN parsing with
pinned IPs (reuses the same `_validated_ip_hosts` guard as PostgreSQL), a
lazily imported synchronous driver (PyMySQL) run in a worker thread, and
``information_schema`` queries mapped into the shape every downstream feature
consumes (relations / columns / constraints / indexes / pk_columns / fk_edges).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import importlib
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlparse

from app.pg_introspect.column_examples import add_column_examples
from app.pg_introspect.dsn_guard import _validated_ip_hosts
from app.sanitize import sanitize_for_storage

_SYSTEM_SCHEMAS = ("mysql", "information_schema", "performance_schema", "sys")
_DEFAULT_PORT = 3306


@dataclass(frozen=True)
class MysqlDsnConfig:
    """Validated MySQL connection parameters with a pinned IP host."""

    host: str  # pinned, validated IP
    server_hostname: str  # original hostname (for TLS/SNI if needed)
    port: int
    user: str
    password: str
    database: str | None


async def _parse_mysql_dsn(dsn: str) -> MysqlDsnConfig:
    """Parse and SSRF-validate a mysql:// DSN; pin the resolved IP."""
    parsed = urlparse(dsn)
    scheme = parsed.scheme.lower().split("+", 1)[0]
    if scheme not in ("mysql", "mariadb"):
        raise ValueError("unsupported MySQL DSN scheme")
    if not parsed.hostname:
        raise ValueError("MySQL DSN must include a host")
    if not parsed.username:
        raise ValueError("MySQL DSN must include a user")
    port = parsed.port or _DEFAULT_PORT
    hosts = await _validated_ip_hosts(parsed.hostname, is_hostaddr=False, port=port)
    database = parsed.path.lstrip("/") or None
    return MysqlDsnConfig(
        host=hosts[0],
        server_hostname=parsed.hostname,
        port=port,
        user=unquote(parsed.username),
        password=unquote(parsed.password or ""),
        database=database,
    )


def _connect(config: MysqlDsnConfig) -> Any:
    try:
        pymysql = importlib.import_module("pymysql")
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "MySQL support requires the PyMySQL package"
        ) from exc
    return pymysql.connect(
        host=config.host,  # pinned IP (SSRF)
        port=config.port,
        user=config.user,
        password=config.password,
        database=config.database,
        connect_timeout=10,
        read_timeout=30,
        write_timeout=30,
    )


def _fetch_dicts(cursor: Any, sql: str, params: tuple[object, ...] = ()) -> list[dict]:
    cursor.execute(sql, params or None)
    names = [d[0] for d in cursor.description or []]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _schema_filter_clause(schema_filter: str | None) -> tuple[str, tuple[object, ...]]:
    if schema_filter:
        return "TABLE_SCHEMA = %s", (schema_filter,)
    placeholders = ", ".join(["%s"] * len(_SYSTEM_SCHEMAS))
    return f"TABLE_SCHEMA NOT IN ({placeholders})", _SYSTEM_SCHEMAS


def rows_to_snapshot(
    version: str,
    schema_filter: str | None,
    tables: list[dict],
    columns: list[dict],
    key_usage: list[dict],
    indexes: list[dict],
) -> dict[str, Any]:
    """Pure transformation: information_schema rows → common snapshot JSON."""
    oid_by_table: dict[tuple[str, str], int] = {}
    relations: list[dict[str, Any]] = []
    for i, row in enumerate(tables, start=1):
        key = (str(row["TABLE_SCHEMA"]), str(row["TABLE_NAME"]))
        oid_by_table[key] = i
        relations.append(
            {
                "relation_oid": i,
                "relation_kind": "v" if str(row.get("TABLE_TYPE", "")).upper() == "VIEW" else "r",
                "schema_name": key[0],
                "relation_name": key[1],
                "relation_comment": str(row.get("TABLE_COMMENT") or "") or None,
            }
        )

    out_columns: list[dict[str, Any]] = []
    for row in columns:
        oid = oid_by_table.get((str(row["TABLE_SCHEMA"]), str(row["TABLE_NAME"])))
        if oid is None:
            continue
        out_columns.append(
            {
                "relation_oid": oid,
                "column_name": str(row["COLUMN_NAME"]),
                "column_position": int(row["ORDINAL_POSITION"]),
                "data_type": str(row.get("COLUMN_TYPE") or row.get("DATA_TYPE") or ""),
                "is_not_null": str(row.get("IS_NULLABLE", "YES")).upper() == "NO",
                "has_default": row.get("COLUMN_DEFAULT") is not None,
                "default_expr": (
                    str(row["COLUMN_DEFAULT"]) if row.get("COLUMN_DEFAULT") is not None else None
                ),
                "column_comment": str(row.get("COLUMN_COMMENT") or "") or None,
            }
        )
    pos_by_oid_col = {
        (c["relation_oid"], c["column_name"]): c["column_position"] for c in out_columns
    }

    pk_columns: list[dict[str, Any]] = []
    fk_edges: list[dict[str, Any]] = []
    constraints: list[dict[str, Any]] = []
    pk_cols_by_oid: dict[int, list[str]] = {}
    for row in key_usage:
        oid = oid_by_table.get((str(row["TABLE_SCHEMA"]), str(row["TABLE_NAME"])))
        if oid is None:
            continue
        col = str(row["COLUMN_NAME"])
        if str(row.get("CONSTRAINT_NAME")) == "PRIMARY":
            pk_columns.append(
                {
                    "relation_oid": oid,
                    "column_name": col,
                    "column_ordinal": int(row.get("ORDINAL_POSITION") or 1),
                }
            )
            pk_cols_by_oid.setdefault(oid, []).append(col)
        elif row.get("REFERENCED_TABLE_NAME"):
            parent = oid_by_table.get(
                (
                    str(row.get("REFERENCED_TABLE_SCHEMA") or row["TABLE_SCHEMA"]),
                    str(row["REFERENCED_TABLE_NAME"]),
                )
            )
            if parent is None:
                continue
            edge_id = len(fk_edges) + 1
            fk_edges.append(
                {
                    "fk_constraint_oid": 100000 + edge_id,
                    "fk_constraint_name": str(row.get("CONSTRAINT_NAME") or f"fk_{edge_id}"),
                    "child_relation_oid": oid,
                    "parent_relation_oid": parent,
                    "child_column_name": col,
                    "parent_column_name": str(row["REFERENCED_COLUMN_NAME"]),
                    "column_ordinal": int(row.get("ORDINAL_POSITION") or 1),
                }
            )

    rel_by_oid = {r["relation_oid"]: r for r in relations}
    for oid, cols in pk_cols_by_oid.items():
        rel = rel_by_oid[oid]
        quoted = ", ".join(f'"{c}"' for c in cols)
        constraints.append(
            {
                "constraint_oid": 200000 + oid,
                "constraint_name": f"pk_{rel['relation_name']}",
                "constraint_type": "p",
                "schema_name": rel["schema_name"],
                "relation_oid": oid,
                "relation_name": rel["relation_name"],
                "constrained_attnums": [pos_by_oid_col.get((oid, c), i + 1) for i, c in enumerate(cols)],
                "constraint_def": f"PRIMARY KEY ({quoted})",
            }
        )
    for edge in fk_edges:
        child_rel = rel_by_oid[edge["child_relation_oid"]]
        parent_rel = rel_by_oid[edge["parent_relation_oid"]]
        constraints.append(
            {
                "constraint_oid": 300000 + edge["fk_constraint_oid"],
                "constraint_name": edge["fk_constraint_name"],
                "constraint_type": "f",
                "schema_name": child_rel["schema_name"],
                "relation_oid": edge["child_relation_oid"],
                "relation_name": child_rel["relation_name"],
                "constrained_attnums": [
                    pos_by_oid_col.get((edge["child_relation_oid"], edge["child_column_name"]), 1)
                ],
                "constraint_def": (
                    f'FOREIGN KEY ("{edge["child_column_name"]}") REFERENCES '
                    f'"{parent_rel["schema_name"]}"."{parent_rel["relation_name"]}" '
                    f'("{edge["parent_column_name"]}")'
                ),
            }
        )

    # group STATISTICS rows into per-index column lists
    grouped: dict[tuple[str, str, str], list[tuple[int, str, bool]]] = {}
    for row in indexes:
        ix_key = (str(row["TABLE_SCHEMA"]), str(row["TABLE_NAME"]), str(row["INDEX_NAME"]))
        grouped.setdefault(ix_key, []).append(
            (
                int(row.get("SEQ_IN_INDEX") or 1),
                str(row["COLUMN_NAME"]),
                not bool(int(row.get("NON_UNIQUE") or 0)),
            )
        )
    out_indexes: list[dict[str, Any]] = []
    for (schema, table, name), ix_cols in sorted(grouped.items()):
        ix_oid = oid_by_table.get((schema, table))
        if ix_oid is None:
            continue
        ordered = [c for _, c, _ in sorted(ix_cols)]
        unique = ix_cols[0][2]
        cols_sql = ", ".join(ordered)
        out_indexes.append(
            {
                "relation_oid": ix_oid,
                "index_name": name,
                "is_unique": unique,
                "is_primary": name == "PRIMARY",
                "index_def": (
                    f"CREATE {'UNIQUE ' if unique else ''}INDEX {name} "
                    f"ON {schema}.{table} ({cols_sql})"
                ),
            }
        )

    snapshot = {
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "server_version": version,
        "source_dialect": "mysql",
        "schema_filter": schema_filter,
        "schemas": sorted({r["schema_name"] for r in relations}),
        "relations": relations,
        "columns": add_column_examples(out_columns),
        "constraints": constraints,
        "indexes": out_indexes,
        "pk_columns": pk_columns,
        "fk_edges": fk_edges,
        "citus_distributed_tables": [],
    }
    return sanitize_for_storage(snapshot)  # type: ignore[return-value]


def _introspect_sync(config: MysqlDsnConfig, schema_filter: str | None) -> dict[str, Any]:
    conn = _connect(config)
    try:
        cursor = conn.cursor()
        version_rows = _fetch_dicts(cursor, "SELECT VERSION() AS v")
        version = str(version_rows[0]["v"]) if version_rows else "unknown"
        where, params = _schema_filter_clause(schema_filter)
        tables = _fetch_dicts(
            cursor,
            "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE, TABLE_COMMENT "
            f"FROM information_schema.TABLES WHERE {where} "
            "ORDER BY TABLE_SCHEMA, TABLE_NAME",
            params,
        )
        columns = _fetch_dicts(
            cursor,
            "SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, ORDINAL_POSITION, "
            "COLUMN_TYPE, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_COMMENT "
            f"FROM information_schema.COLUMNS WHERE {where} "
            "ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION",
            params,
        )
        key_usage = _fetch_dicts(
            cursor,
            "SELECT CONSTRAINT_NAME, TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME, "
            "ORDINAL_POSITION, REFERENCED_TABLE_SCHEMA, REFERENCED_TABLE_NAME, "
            "REFERENCED_COLUMN_NAME "
            f"FROM information_schema.KEY_COLUMN_USAGE WHERE {where} "
            "ORDER BY TABLE_SCHEMA, TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION",
            params,
        )
        indexes = _fetch_dicts(
            cursor,
            "SELECT TABLE_SCHEMA, TABLE_NAME, INDEX_NAME, NON_UNIQUE, "
            "SEQ_IN_INDEX, COLUMN_NAME "
            f"FROM information_schema.STATISTICS WHERE {where} "
            "ORDER BY TABLE_SCHEMA, TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX",
            params,
        )
        return rows_to_snapshot(version, schema_filter, tables, columns, key_usage, indexes)
    finally:
        conn.close()


async def introspect_mysql(dsn: str, schema_filter: str | None) -> dict[str, Any]:
    """Introspect a MySQL/MariaDB database and return a snapshot JSON."""
    config = await _parse_mysql_dsn(dsn)
    return await asyncio.to_thread(_introspect_sync, config, schema_filter)


def _probe_sync(config: MysqlDsnConfig) -> str:
    conn = _connect(config)
    try:
        cursor = conn.cursor()
        rows = _fetch_dicts(cursor, "SELECT VERSION() AS v")
        return str(rows[0]["v"]) if rows else "unknown"
    finally:
        conn.close()


async def probe_mysql(dsn: str) -> str:
    """SSRF-guarded connectivity check: connect and return the server version."""
    config = await _parse_mysql_dsn(dsn)
    return await asyncio.to_thread(_probe_sync, config)
