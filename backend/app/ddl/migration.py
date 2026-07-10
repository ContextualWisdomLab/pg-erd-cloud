"""Generate migration SQL that transforms one schema snapshot into another.

This bridges two existing capabilities -- the name-based structural diff
(``app.diff.schema_diff``) and the dialect-aware DDL rendering
(``app.ddl.export``) -- into an actionable output: the ``CREATE``/``ALTER``/
``DROP`` statements needed to move a database from the *base* snapshot to the
*target* snapshot.

Design notes
------------
* Tables/columns/FKs are matched **by name**, never by ``relation_oid`` (which
  is reassigned on every introspection run) -- the same correctness rule the
  diff enforces.
* PostgreSQL is the reference dialect and is emitted precisely; Snowflake output
  maps column types via the DDL exporter and uses Snowflake ALTER syntax.
* The output is advisory: destructive changes (DROP TABLE/COLUMN) are emitted so
  a human reviews them before running. Primary-key changes are noted as comments
  because they usually require data-aware handling.
"""

from __future__ import annotations

from typing import Any

from app.ddl.export import (
    DdlDialect,
    _mapped_data_type,
    _normalize_dialect,
    _q,
    _qname,
    _snapshot_source_dialect,
)
from app.diff.schema_diff import _index_snapshot


def _col_type(column_name: str, col: dict[str, Any], source: DdlDialect, target: DdlDialect) -> str:
    return _mapped_data_type(
        {"data_type": col.get("data_type"), "column_name": column_name}, source, target
    )


def _column_clause(name: str, col: dict[str, Any], source: DdlDialect, target: DdlDialect) -> str:
    clause = f"{_q(name)} {_col_type(name, col, source, target)}"
    if col.get("is_not_null"):
        clause += " NOT NULL"
    return clause


def _create_table_sql(tbl: dict[str, Any], source: DdlDialect, target: DdlDialect) -> str:
    qname = _qname(tbl["schema_name"], tbl["relation_name"])
    lines = [
        "  " + _column_clause(name, col, source, target)
        for name, col in tbl["columns"].items()
    ]
    if tbl.get("pk"):
        cols = ", ".join(_q(c) for c in tbl["pk"])
        lines.append(f"  PRIMARY KEY ({cols})")
    body = ",\n".join(lines)
    return f"CREATE TABLE {qname} (\n{body}\n);"


def _alter_column_type_sql(qname: str, name: str, type_sql: str, target: DdlDialect) -> str:
    if target == "snowflake":
        return f"ALTER TABLE {qname} ALTER COLUMN {_q(name)} SET DATA TYPE {type_sql};"
    return f"ALTER TABLE {qname} ALTER COLUMN {_q(name)} TYPE {type_sql};"


def _alter_table_sql(
    base_tbl: dict[str, Any],
    target_tbl: dict[str, Any],
    source: DdlDialect,
    target: DdlDialect,
) -> list[str]:
    qname = _qname(target_tbl["schema_name"], target_tbl["relation_name"])
    stmts: list[str] = []
    base_cols = base_tbl["columns"]
    target_cols = target_tbl["columns"]

    for name, col in target_cols.items():
        if name not in base_cols:
            stmts.append(
                f"ALTER TABLE {qname} ADD COLUMN {_column_clause(name, col, source, target)};"
            )
    for name in base_cols:
        if name not in target_cols:
            stmts.append(f"ALTER TABLE {qname} DROP COLUMN {_q(name)};")
    for name, col in target_cols.items():
        if name not in base_cols:
            continue
        old = base_cols[name]
        old_type = _col_type(name, old, source, target)
        new_type = _col_type(name, col, source, target)
        if old_type != new_type:
            stmts.append(_alter_column_type_sql(qname, name, new_type, target))
        if bool(old.get("is_not_null")) != bool(col.get("is_not_null")):
            action = "SET NOT NULL" if col.get("is_not_null") else "DROP NOT NULL"
            stmts.append(f"ALTER TABLE {qname} ALTER COLUMN {_q(name)} {action};")

    if base_tbl.get("pk", []) != target_tbl.get("pk", []):
        cols = ", ".join(target_tbl.get("pk", []))
        stmts.append(
            f"-- PRIMARY KEY of {qname} changed to ({cols}); review before applying."
        )
    if base_tbl.get("comment") != target_tbl.get("comment") and target == "postgresql":
        comment = target_tbl.get("comment")
        if comment:
            escaped = str(comment).replace("'", "''")
            stmts.append(f"COMMENT ON TABLE {qname} IS '{escaped}';")
        else:
            stmts.append(f"COMMENT ON TABLE {qname} IS NULL;")
    return stmts


def _fk_endpoints(fk: dict[str, Any], tables: dict[str, Any]) -> tuple[str, str] | None:
    child = tables.get(fk["child_table"])
    parent = tables.get(fk["parent_table"])
    if child is None or parent is None:
        return None
    return (
        _qname(child["schema_name"], child["relation_name"]),
        _qname(parent["schema_name"], parent["relation_name"]),
    )


def _add_fk_sql(fk: dict[str, Any], tables: dict[str, Any]) -> str | None:
    ends = _fk_endpoints(fk, tables)
    if ends is None:
        return None
    child_q, parent_q = ends
    child_cols = ", ".join(_q(c) for c in fk["child_columns"])
    parent_cols = ", ".join(_q(c) for c in fk["parent_columns"])
    name = fk.get("name")
    constraint = f"CONSTRAINT {_q(name)} " if name else ""
    return (
        f"ALTER TABLE {child_q} ADD {constraint}FOREIGN KEY ({child_cols}) "
        f"REFERENCES {parent_q} ({parent_cols});"
    )


def _drop_fk_sql(fk: dict[str, Any], tables: dict[str, Any]) -> str | None:
    ends = _fk_endpoints(fk, tables)
    if ends is None:
        return None
    child_q, _ = ends
    name = fk.get("name")
    if name:
        return f"ALTER TABLE {child_q} DROP CONSTRAINT {_q(name)};"
    child_cols = ", ".join(_q(c) for c in fk["child_columns"])
    return (
        f"-- FOREIGN KEY on {child_q} ({child_cols}) was removed but has no "
        "constraint name; drop it manually."
    )


def _create_missing_schema_sql(
    base_tables: dict[str, Any], target_tables: dict[str, Any]
) -> list[str]:
    base_schemas = {
        tbl.get("schema_name")
        for tbl in base_tables.values()
        if isinstance(tbl.get("schema_name"), str) and tbl.get("schema_name")
    }
    missing = {
        tbl.get("schema_name")
        for key, tbl in target_tables.items()
        if key not in base_tables
        and isinstance(tbl.get("schema_name"), str)
        and tbl.get("schema_name")
        and tbl.get("schema_name") not in base_schemas
    }
    return [f"CREATE SCHEMA IF NOT EXISTS {_q(schema)};" for schema in sorted(missing)]


def snapshot_diff_to_migration_sql(
    base: dict[str, Any] | None,
    target: dict[str, Any] | None,
    target_dialect: str = "postgresql",
) -> str:
    """Return SQL that migrates the *base* schema to the *target* schema.

    Matching is by name (oid-independent). Returns a ``-- No schema changes.``
    marker when the two snapshots are structurally identical.
    """
    dialect = _normalize_dialect(target_dialect)
    source = _snapshot_source_dialect(target or {})
    b = _index_snapshot(base)
    t = _index_snapshot(target)
    b_tables, t_tables = b["tables"], t["tables"]

    stmts: list[str] = []
    removed_tables = set(b_tables) - set(t_tables)

    base_fks, target_fks = b["fks"], t["fks"]
    for sig, fk in base_fks.items():
        if sig in target_fks:
            continue
        child_table = fk.get("child_table")
        parent_table = fk.get("parent_table")
        if child_table in removed_tables and parent_table not in removed_tables:
            continue
        sql = _drop_fk_sql(fk, b_tables)
        if sql:
            stmts.append(sql)

    # Drop constraints before table/column removals so referenced objects unlock.
    for key, tbl in b_tables.items():
        if key not in t_tables:
            stmts.append(
                f"DROP TABLE IF EXISTS {_qname(tbl['schema_name'], tbl['relation_name'])};"
            )
    stmts.extend(_create_missing_schema_sql(b_tables, t_tables))
    for key, tbl in t_tables.items():
        if key not in b_tables:
            stmts.append(_create_table_sql(tbl, source, dialect))
    for key, tbl in t_tables.items():
        if key in b_tables:
            stmts.extend(_alter_table_sql(b_tables[key], tbl, source, dialect))

    for sig, fk in target_fks.items():
        if sig not in base_fks:
            sql = _add_fk_sql(fk, t_tables)
            if sql:
                stmts.append(sql)

    if not stmts:
        return "-- No schema changes.\n"
    header = f"-- Migration ({dialect}): base -> target\n"
    return header + "\n".join(stmts) + "\n"
