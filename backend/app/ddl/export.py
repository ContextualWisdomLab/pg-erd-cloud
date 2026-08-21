from __future__ import annotations

import re
from typing import Literal

DdlDialect = Literal["postgresql", "snowflake"]


def _rows(snapshot: dict, key: str) -> list[dict]:
    """Return ``snapshot[key]`` as a list of dict rows, tolerating junk.

    Snapshot payloads are weakly-typed JSON; a malformed key (missing, or not a
    list, or holding non-dict entries) must degrade to "no rows" rather than
    raise. Mirrors the defensive contract already used by the spec/lint
    generators (``app.spec.reversing._rows`` etc.).
    """

    value = snapshot.get(key)
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _normalize_dialect(dialect: str) -> DdlDialect:
    normalized = dialect.lower().replace("_", "-")
    if normalized in ("postgres", "postgresql", "pg"):
        return "postgresql"
    if normalized in ("snowflake", "sf"):
        return "snowflake"
    raise ValueError(f"unsupported DDL dialect: {dialect}")


def _snapshot_source_dialect(snapshot: dict) -> DdlDialect:
    for key in ("source_dialect", "database_dialect", "dialect"):
        value = snapshot.get(key)
        if isinstance(value, str):
            try:
                return _normalize_dialect(value)
            except ValueError:
                continue
    return "postgresql"


def _q(ident: str) -> str:
    """Quote a SQL identifier."""

    # Quote identifier with double-quotes, escaping internal quotes.
    return '"' + ident.replace('"', '""') + '"'


def _qname(schema: str, name: str) -> str:
    """Quote a schema-qualified name."""
    return f"{_q(schema)}.{_q(name)}"


def _tablespace_clause(tablespace: object) -> str:
    return f" TABLESPACE {_q(tablespace)}" if isinstance(tablespace, str) else ""


_CREATE_INDEX_RE = re.compile(
    r"^CREATE\s+(UNIQUE\s+)?INDEX\s+(?!CONCURRENTLY\b)",
    flags=re.IGNORECASE,
)


def _index_def_with_concurrently(index_def: str) -> str:
    """Add CONCURRENTLY to a PostgreSQL CREATE INDEX statement."""

    def replacement(match: re.Match[str]) -> str:
        unique = match.group(1) or ""
        return f"CREATE {unique}INDEX CONCURRENTLY "

    return _CREATE_INDEX_RE.sub(replacement, index_def, count=1)


def _normalize_type_text(data_type: str) -> str:
    return re.sub(r"\s+", " ", data_type.strip().lower())


def _postgres_type_to_snowflake(column: dict) -> str:
    base_type = column.get("domain_base_type")
    if isinstance(base_type, str):
        # Re-map using the domain's base type, but clear domain_base_type so the
        # recursion terminates (otherwise a column carrying a string
        # domain_base_type recurses forever -> RecursionError / DoS).
        return _postgres_type_to_snowflake(
            {**column, "data_type": base_type, "domain_base_type": None}
        )

    data_type = column.get("data_type")
    if not isinstance(data_type, str):
        return "VARCHAR"

    normalized = _normalize_type_text(data_type)
    if (
        column.get("array_dimensions")
        or normalized.endswith("[]")
        or normalized.startswith("array")
    ):
        return "ARRAY"

    exact = {
        "smallint": "NUMBER(5,0)",
        "integer": "NUMBER(10,0)",
        "bigint": "NUMBER(19,0)",
        "real": "FLOAT",
        "double precision": "FLOAT",
        "boolean": "BOOLEAN",
        "text": "VARCHAR",
        "json": "VARIANT",
        "jsonb": "VARIANT",
        "bytea": "BINARY",
        "date": "DATE",
        "uuid": "VARCHAR(36)",
        "inet": "VARCHAR",
        "cidr": "VARCHAR",
        "macaddr": "VARCHAR",
        "macaddr8": "VARCHAR",
        "xml": "VARCHAR",
    }
    if normalized in exact:
        return exact[normalized]

    numeric = re.match(
        r"^(numeric|decimal)\s*(?:\((\d+)(?:\s*,\s*(\d+))?\))?$",
        normalized,
    )
    if numeric:
        precision = numeric.group(2)
        scale = numeric.group(3)
        if precision and scale:
            return f"NUMBER({precision},{scale})"
        if precision:
            return f"NUMBER({precision},0)"
        return "NUMBER"

    varchar = re.match(r"^(character varying|varchar)\s*(?:\((\d+)\))?$", normalized)
    if varchar:
        return f"VARCHAR({varchar.group(2)})" if varchar.group(2) else "VARCHAR"

    char = re.match(r"^(character|char)\s*(?:\((\d+)\))?$", normalized)
    if char:
        return f"CHAR({char.group(2)})" if char.group(2) else "CHAR"

    if normalized.startswith("timestamp") and "with time zone" in normalized:
        return "TIMESTAMP_TZ"
    if normalized.startswith("timestamp"):
        return "TIMESTAMP_NTZ"
    if normalized.startswith("time"):
        return "TIME"
    if normalized.startswith("interval"):
        return "VARCHAR"

    if column.get("type_kind") == "e":
        return "VARCHAR"

    return "VARCHAR"


def _snowflake_type_to_postgres(column: dict) -> str:
    data_type = column.get("data_type")
    if not isinstance(data_type, str):
        return "text"

    normalized = _normalize_type_text(data_type)
    exact = {
        "boolean": "boolean",
        "bool": "boolean",
        "date": "date",
        "time": "time",
        "float": "double precision",
        "float4": "real",
        "float8": "double precision",
        "double": "double precision",
        "double precision": "double precision",
        "real": "real",
        "binary": "bytea",
        "varbinary": "bytea",
        "variant": "jsonb",
        "object": "jsonb",
        "array": "jsonb",
        "geography": "jsonb",
        "geometry": "jsonb",
    }
    if normalized in exact:
        return exact[normalized]

    number = re.match(
        r"^(number|numeric|decimal)\s*(?:\((\d+)(?:\s*,\s*(\d+))?\))?$",
        normalized,
    )
    if number:
        precision = number.group(2)
        scale = number.group(3)
        if precision and scale:
            return f"numeric({precision},{scale})"
        if precision:
            return f"numeric({precision},0)"
        return "numeric"

    varchar = re.match(r"^(varchar|string|text)\s*(?:\((\d+)\))?$", normalized)
    if varchar:
        return f"character varying({varchar.group(2)})" if varchar.group(2) else "text"

    char = re.match(r"^(char|character)\s*(?:\((\d+)\))?$", normalized)
    if char:
        return f"character({char.group(2)})" if char.group(2) else "character"

    if normalized.startswith("timestamp_tz") or normalized.startswith("timestamp_ltz"):
        return "timestamp with time zone"
    if normalized.startswith("timestamp_ntz") or normalized.startswith("timestamp"):
        return "timestamp without time zone"

    return "text"


def _mapped_data_type(column: dict, source: DdlDialect, target: DdlDialect) -> str:
    data_type = column.get("data_type")
    if not isinstance(data_type, str):
        return "text" if target == "postgresql" else "VARCHAR"
    if source == target:
        return data_type
    if source == "postgresql" and target == "snowflake":
        return _postgres_type_to_snowflake(column)
    if source == "snowflake" and target == "postgresql":
        return _snowflake_type_to_postgres(column)
    return data_type


def _column_default_clause(default_expr: object, target: DdlDialect) -> str | None:
    if not isinstance(default_expr, str):
        return None
    expr = default_expr.strip()
    if not expr:
        return None
    if target == "postgresql":
        return f"DEFAULT {expr}"

    upper = expr.upper()
    if "::" in expr or "NEXTVAL(" in upper:
        return None
    if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", expr):
        return f"DEFAULT {expr}"
    if re.fullmatch(r"'(?:''|[^'])*'", expr):
        return f"DEFAULT {expr}"
    if upper in ("TRUE", "FALSE"):
        return f"DEFAULT {upper}"
    if upper in ("NOW()", "CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP()"):
        return "DEFAULT CURRENT_TIMESTAMP()"
    if upper in ("CURRENT_DATE", "CURRENT_DATE()"):
        return "DEFAULT CURRENT_DATE()"
    if upper in ("CURRENT_TIME", "CURRENT_TIME()"):
        return "DEFAULT CURRENT_TIME()"
    if upper in ("GEN_RANDOM_UUID()", "UUID_GENERATE_V4()"):
        return "DEFAULT UUID_STRING()"
    return None


def _snapshot_tables(snapshot: dict) -> list[dict]:
    return [
        r
        for r in _rows(snapshot, "relations")
        if r.get("relation_kind") in ("r", "p")
    ]


def _group_by_relation(rows: object) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = {}
    if not isinstance(rows, list):
        return grouped
    for row in rows:
        if not isinstance(row, dict):
            continue
        oid = row.get("relation_oid")
        if isinstance(oid, int):
            grouped.setdefault(oid, []).append(row)
    return grouped


def _constraint_column_names(
    constraint: dict, cols_by_oid: dict[int, list[dict]]
) -> list[str]:
    oid = constraint.get("relation_oid")
    attnums = constraint.get("constrained_attnums")
    if not isinstance(oid, int) or not isinstance(attnums, list):
        return []

    cols_by_attnum: dict[int, str] = {}
    for col in cols_by_oid.get(oid, []):
        position = col.get("column_position")
        name = col.get("column_name")
        if isinstance(position, int) and isinstance(name, str):
            cols_by_attnum[position] = name

    names: list[str] = []
    for attnum in attnums:
        if not isinstance(attnum, int):
            return []
        name = cols_by_attnum.get(attnum)
        if name is None:
            return []
        names.append(name)
    return names


def _render_schemas(tables: list[dict], lines: list[str]) -> None:
    schemas: set[str] = set()
    for table in tables:
        schema_name = table.get("schema_name")
        if isinstance(schema_name, str):
            schemas.add(schema_name)

    for s in sorted(schemas):
        lines.append(f"CREATE SCHEMA IF NOT EXISTS {_q(s)};")
    if schemas:
        lines.append("")


def _render_foreign_keys(constraints: list[dict], lines: list[str]) -> None:
    fk_cons = [c for c in constraints if c.get("constraint_type") == "f"]
    if fk_cons:
        lines.append("-- Foreign keys")
    for con in fk_cons:
        schema = con.get("schema_name")
        table = con.get("relation_name")
        cname = con.get("constraint_name")
        cdef = con.get("constraint_def")
        if not (
            isinstance(schema, str)
            and isinstance(table, str)
            and isinstance(cname, str)
            and isinstance(cdef, str)
        ):
            continue
        lines.append(
            f"ALTER TABLE {_qname(schema, table)} ADD CONSTRAINT {_q(cname)} {cdef};"
        )
    if fk_cons:
        lines.append("")


def _render_indexes_pg(indexes: list[dict], lines: list[str]) -> None:
    if indexes:
        lines.append("-- Indexes (CONCURRENTLY; run outside a transaction)")
    for ix in indexes:
        ix_def = ix.get("index_def")
        if not isinstance(ix_def, str):
            continue
        ix_def = ix_def.strip().rstrip(";")
        ix_def = _index_def_with_concurrently(ix_def)
        table_options = _tablespace_clause(ix.get("index_tablespace_name"))
        if table_options and " TABLESPACE " not in ix_def.upper():
            ix_def = f"{ix_def}{table_options}"
        lines.append(ix_def + ";")


def _render_table_columns_pg(
    oid: int,
    cols_by_oid: dict[int, list[dict]],
    source_dialect: DdlDialect,
) -> list[str]:
    col_defs: list[str] = []
    for c in sorted(
        cols_by_oid.get(oid, []),
        key=lambda x: int(x.get("column_position") or 0),
    ):
        col_name = c.get("column_name")
        if not isinstance(col_name, str):
            continue
        data_type = _mapped_data_type(c, source_dialect, "postgresql")
        parts = [f"{_q(col_name)} {data_type}"]
        if c.get("has_default"):
            default_clause = _column_default_clause(c.get("default_expr"), "postgresql")
            if default_clause:
                parts.append(default_clause)
        if c.get("is_not_null") is True:
            parts.append("NOT NULL")
        col_defs.append(" ".join(parts))
    return col_defs


def _render_table_constraints_pg(
    oid: int,
    constraints_by_oid: dict[int, list[dict]],
) -> list[str]:
    table_cons: list[str] = []
    for con in constraints_by_oid.get(oid, []):
        ctype = con.get("constraint_type")
        if ctype not in ("p", "u", "c"):
            continue
        cname = con.get("constraint_name")
        cdef = con.get("constraint_def")
        if isinstance(cname, str) and isinstance(cdef, str):
            table_cons.append(f"CONSTRAINT {_q(cname)} {cdef}")
    return table_cons


def snapshot_json_to_sql(snapshot: dict, target_dialect: str = "postgresql") -> str:
    """Render a captured schema snapshot as SQL for the requested dialect."""
    target = _normalize_dialect(target_dialect)
    if target == "snowflake":
        return _snapshot_json_to_snowflake_sql(snapshot)
    return _snapshot_json_to_postgresql_sql(snapshot)


def _render_table_pg(
    t: dict,
    cols_by_oid: dict[int, list[dict]],
    constraints_by_oid: dict[int, list[dict]],
    source_dialect: DdlDialect,
) -> list[str]:
    schema = t.get("schema_name")
    name = t.get("relation_name")
    oid = t.get("relation_oid")
    kind = t.get("relation_kind")
    tablespace = t.get("tablespace_name")
    partition_key = t.get("partition_key")
    partition_bound = t.get("partition_bound")
    partition_parent_schema = t.get("partition_parent_schema")
    partition_parent_name = t.get("partition_parent_name")
    is_partition = t.get("is_partition") is True
    if not (isinstance(schema, str) and isinstance(name, str) and isinstance(oid, int)):
        return []

    lines: list[str] = []
    table_options = _tablespace_clause(tablespace)
    if (
        is_partition
        and isinstance(partition_parent_schema, str)
        and isinstance(partition_parent_name, str)
        and isinstance(partition_bound, str)
    ):
        partition_clause = (
            f" PARTITION BY {partition_key}" if isinstance(partition_key, str) else ""
        )
        lines.append(
            f"CREATE TABLE IF NOT EXISTS {_qname(schema, name)} PARTITION OF {_qname(partition_parent_schema, partition_parent_name)} {partition_bound}{partition_clause}{table_options};"
        )
        lines.append("")
        return lines

    if kind == "p" and not isinstance(partition_key, str):
        lines.append(
            f"-- NOTE: {_qname(schema, name)} is partitioned; partition definition not included in MVP export"
        )

    col_defs = _render_table_columns_pg(oid, cols_by_oid, source_dialect)
    table_cons = _render_table_constraints_pg(oid, constraints_by_oid)

    all_defs = col_defs + table_cons
    lines.append(f"CREATE TABLE IF NOT EXISTS {_qname(schema, name)} (")
    for i, d in enumerate(all_defs):
        comma = "," if i < len(all_defs) - 1 else ""
        lines.append(f"  {d}{comma}")
    partition_clause = (
        f" PARTITION BY {partition_key}"
        if kind == "p" and isinstance(partition_key, str)
        else ""
    )
    lines.append(f"){partition_clause}{table_options};")
    lines.append("")
    return lines


def _snapshot_json_to_postgresql_sql(snapshot: dict) -> str:
    """Generate PostgreSQL DDL from a captured snapshot.

    This is MVP-grade forward engineering (export):
    - Creates schemas and tables (columns only)
    - Adds PK/UNIQUE/CHECK inside CREATE TABLE
    - Adds FKs after all tables (order-safe)
    - Adds indexes using saved pg_get_indexdef output

    Limitations (intentional, MVP): partitioning clauses and some table options are not reconstructed.
    """

    columns = _rows(snapshot, "columns")
    constraints = _rows(snapshot, "constraints")
    indexes = _rows(snapshot, "indexes")
    source_dialect = _snapshot_source_dialect(snapshot)

    tables = _snapshot_tables(snapshot)

    cols_by_oid = _group_by_relation(columns)
    constraints_by_oid = _group_by_relation(constraints)

    lines: list[str] = []
    lines.append("-- Generated by pg-erd-cloud (MVP)\n")
    _render_schemas(tables, lines)

    # CREATE TABLE + inline constraints (PK/UNIQUE/CHECK)
    for t in tables:
        lines.extend(
            _render_table_pg(t, cols_by_oid, constraints_by_oid, source_dialect)
        )

    # FKs after tables
    _render_foreign_keys(constraints, lines)

    # Indexes (use saved pg_get_indexdef output)
    _render_indexes_pg(indexes, lines)

    lines.append("")
    return "\n".join(lines)


def _render_table_columns_snowflake(
    oid: int,
    cols_by_oid: dict[int, list[dict]],
    source_dialect: DdlDialect,
) -> list[str]:
    col_defs: list[str] = []
    for c in sorted(
        cols_by_oid.get(oid, []),
        key=lambda x: int(x.get("column_position") or 0),
    ):
        col_name = c.get("column_name")
        if not isinstance(col_name, str):
            continue
        parts = [f"{_q(col_name)} {_mapped_data_type(c, source_dialect, 'snowflake')}"]
        if c.get("has_default"):
            default_clause = _column_default_clause(c.get("default_expr"), "snowflake")
            if default_clause:
                parts.append(default_clause)
        if c.get("is_not_null") is True:
            parts.append("NOT NULL")
        col_defs.append(" ".join(parts))
    return col_defs


def _render_table_constraints_snowflake(
    oid: int,
    constraints_by_oid: dict[int, list[dict]],
    cols_by_oid: dict[int, list[dict]],
) -> tuple[list[str], list[str]]:
    table_cons: list[str] = []
    skipped_checks: list[str] = []
    for con in constraints_by_oid.get(oid, []):
        ctype = con.get("constraint_type")
        cname = con.get("constraint_name")
        cdef = con.get("constraint_def")
        if not (isinstance(cname, str) and isinstance(cdef, str)):
            continue
        if ctype in ("p", "u"):
            col_names = _constraint_column_names(con, cols_by_oid)
            if col_names:
                keyword = "PRIMARY KEY" if ctype == "p" else "UNIQUE"
                quoted_cols = ", ".join(_q(name) for name in col_names)
                table_cons.append(f"CONSTRAINT {_q(cname)} {keyword} ({quoted_cols})")
            else:
                table_cons.append(f"CONSTRAINT {_q(cname)} {cdef}")
        elif ctype == "c":
            skipped_checks.append(cname)
    return table_cons, skipped_checks


def _render_indexes_snowflake(indexes: list[dict], lines: list[str]) -> None:
    if indexes:
        lines.append("-- Indexes")
    for ix in indexes:
        if not isinstance(ix, dict):
            continue
        ix_name = ix.get("index_name")
        table_schema = ix.get("table_schema_name")
        table_name = ix.get("table_name")
        if (
            isinstance(ix_name, str)
            and isinstance(table_schema, str)
            and isinstance(table_name, str)
        ):
            lines.append(
                f"-- NOTE: PostgreSQL index {_q(ix_name)} on {_qname(table_schema, table_name)} is not emitted for Snowflake; consider clustering/search optimization as needed."
            )
        else:
            lines.append(
                "-- NOTE: PostgreSQL index metadata is not emitted for Snowflake."
            )


def _snapshot_json_to_snowflake_sql(snapshot: dict) -> str:
    """Generate Snowflake DDL from a captured PostgreSQL/Snowflake snapshot."""

    source_dialect = _snapshot_source_dialect(snapshot)
    columns = _rows(snapshot, "columns")
    constraints = _rows(snapshot, "constraints")
    indexes = _rows(snapshot, "indexes")

    tables = _snapshot_tables(snapshot)
    cols_by_oid = _group_by_relation(columns)
    constraints_by_oid = _group_by_relation(constraints)

    lines: list[str] = []
    lines.append("-- Generated by pg-erd-cloud (MVP) for Snowflake\n")
    _render_schemas(tables, lines)

    for t in tables:
        schema = t.get("schema_name")
        name = t.get("relation_name")
        oid = t.get("relation_oid")
        if not (
            isinstance(schema, str) and isinstance(name, str) and isinstance(oid, int)
        ):
            continue

        col_defs = _render_table_columns_snowflake(oid, cols_by_oid, source_dialect)
        table_cons, skipped_checks = _render_table_constraints_snowflake(
            oid, constraints_by_oid, cols_by_oid
        )

        all_defs = col_defs + table_cons
        lines.append(f"CREATE TABLE IF NOT EXISTS {_qname(schema, name)} (")
        for i, d in enumerate(all_defs):
            comma = "," if i < len(all_defs) - 1 else ""
            lines.append(f"  {d}{comma}")
        lines.append(");")
        for cname in skipped_checks:
            lines.append(
                f"-- NOTE: skipped PostgreSQL CHECK constraint {_q(cname)} on {_qname(schema, name)} for Snowflake export."
            )
        if isinstance(t.get("tablespace_name"), str):
            lines.append(
                f"-- NOTE: skipped PostgreSQL TABLESPACE {_q(t['tablespace_name'])} on {_qname(schema, name)} for Snowflake export."
            )
        if t.get("relation_kind") == "p" or t.get("is_partition") is True:
            lines.append(
                f"-- NOTE: skipped PostgreSQL partition metadata on {_qname(schema, name)} for Snowflake export."
            )
        lines.append("")

    _render_foreign_keys(constraints, lines)

    _render_indexes_snowflake(indexes, lines)

    lines.append("")
    return "\n".join(lines)
