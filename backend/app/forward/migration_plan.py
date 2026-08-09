"""Compile canonical schema models into immutable structured migration plans.

The compiler emits both SQL and the metadata the executor needs.  Execution
must consume these statements directly; it must not re-parse browser-supplied
SQL to rediscover authority, ordering, risk, privileges, or preconditions.
Compiler v1 intentionally supports a transactional subset and turns every
unsupported semantic change into a blocking finding.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from app.forward.schema_model import canonicalize_schema_model, schema_model_digest

COMPILER_VERSION = "pg-erd-forward/v1"


def _quote_identifier(identifier: str) -> str:
    """Return a PostgreSQL delimited identifier preserving exact spelling."""

    return '"' + identifier.replace('"', '""') + '"'


def _qualified_name(schema_name: str, table_name: str) -> str:
    return f"{_quote_identifier(schema_name)}.{_quote_identifier(table_name)}"


def _tables(model: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (schema["schema_name"], table["table_name"]): table
        for schema in model["schemas"]
        for table in schema["tables"]
    }


def _risk(
    severity: str,
    *,
    lock_mode: str,
    possible_rewrite: bool = False,
    table_scan: bool = False,
    data_loss: bool = False,
    detail: str,
) -> dict[str, Any]:
    return {
        "severity": severity,
        "lock_mode": lock_mode,
        "possible_rewrite": possible_rewrite,
        "table_scan": table_scan,
        "data_loss": data_loss,
        "detail": detail,
    }


def _statement(
    *,
    kind: str,
    target: str,
    object_ref: dict[str, str],
    sql: str,
    dependencies: list[str],
    dependency_refs: list[dict[str, str]],
    reversible: bool,
    risk: dict[str, Any],
    required_privileges: list[str],
    preconditions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "target": target,
        "object_ref": object_ref,
        "sql": sql,
        "transactional": True,
        "dependencies": dependencies,
        "dependency_refs": dependency_refs,
        "reversible": reversible,
        "risk": risk,
        "required_privileges": required_privileges,
        "preconditions": preconditions or [],
    }


def _column_sql(column: Mapping[str, Any]) -> str:
    sql = f"{_quote_identifier(column['column_name'])} {column['data_type']}"
    if not column["nullable"]:
        sql += " NOT NULL"
    return sql


def _create_table_statement(
    schema_name: str, table: Mapping[str, Any]
) -> dict[str, Any]:
    clauses = [_column_sql(column) for column in table["columns"]]
    primary_key = table.get("primary_key")
    if primary_key:
        columns = ", ".join(
            _quote_identifier(column) for column in primary_key["columns"]
        )
        deferrability = ""
        if primary_key["deferrable"]:
            deferrability = " DEFERRABLE"
            if primary_key["initially_deferred"]:
                deferrability += " INITIALLY DEFERRED"
        clauses.append(
            f"CONSTRAINT {_quote_identifier(primary_key['constraint_name'])} "
            f"PRIMARY KEY ({columns}){deferrability}"
        )
    table_name = table["table_name"]
    target = f"{schema_name}.{table_name}"
    sql = f"CREATE TABLE {_qualified_name(schema_name, table_name)} ({', '.join(clauses)});"
    return _statement(
        kind="create_table",
        target=target,
        object_ref={"schema_name": schema_name, "table_name": table_name},
        sql=sql,
        dependencies=[f"schema:{schema_name}"],
        dependency_refs=[{"schema_name": schema_name}],
        reversible=True,
        risk=_risk(
            "safe",
            lock_mode="ACCESS EXCLUSIVE",
            detail="Creates a new table; no existing rows are modified.",
        ),
        required_privileges=["CREATE"],
    )


def _compile_table_changes(
    schema_name: str,
    table_name: str,
    base: Mapping[str, Any],
    target: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    qualified = _qualified_name(schema_name, table_name)
    object_name = f"{schema_name}.{table_name}"
    statements: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    if base.get("primary_key") != target.get("primary_key"):
        blockers.append(
            {
                "code": "primary_key_change_unsupported",
                "object": object_name,
                "object_ref": {
                    "schema_name": schema_name,
                    "table_name": table_name,
                },
                "detail": "Changing an existing primary key is not supported by compiler v1.",
            }
        )
    base_columns = {column["column_name"]: column for column in base["columns"]}
    target_columns = {column["column_name"]: column for column in target["columns"]}
    if base.get("comment") != target.get("comment"):
        blockers.append(
            {
                "code": "table_comment_change_unsupported",
                "object": object_name,
                "object_ref": {
                    "schema_name": schema_name,
                    "table_name": table_name,
                },
                "detail": "Changing a table comment is not supported by compiler v1.",
            }
        )
    for column_name in sorted(set(base_columns) & set(target_columns)):
        before = base_columns[column_name]
        after = target_columns[column_name]
        if before.get("comment") != after.get("comment"):
            blockers.append(
                {
                    "code": "column_comment_change_unsupported",
                    "object": f"{object_name}.{column_name}",
                    "object_ref": {
                        "schema_name": schema_name,
                        "table_name": table_name,
                        "column_name": column_name,
                    },
                    "detail": "Changing a column comment is not supported by compiler v1.",
                }
            )
        if before["ordinal_position"] != after["ordinal_position"]:
            blockers.append(
                {
                    "code": "column_order_change_unsupported",
                    "object": f"{object_name}.{column_name}",
                    "object_ref": {
                        "schema_name": schema_name,
                        "table_name": table_name,
                        "column_name": column_name,
                    },
                    "detail": "Reordering an existing column is not supported by compiler v1.",
                }
            )
    maximum_existing_ordinal = max(
        (int(column["ordinal_position"]) for column in base_columns.values()),
        default=0,
    )
    added_column_names = sorted(
        set(target_columns) - set(base_columns),
        key=lambda name: (target_columns[name]["ordinal_position"], name),
    )
    expected_added_ordinals = list(
        range(
            maximum_existing_ordinal + 1,
            maximum_existing_ordinal + len(added_column_names) + 1,
        )
    )
    for index, column_name in enumerate(added_column_names):
        column = target_columns[column_name]
        if column.get("comment") is not None:
            blockers.append(
                {
                    "code": "column_comment_change_unsupported",
                    "object": f"{object_name}.{column_name}",
                    "object_ref": {
                        "schema_name": schema_name,
                        "table_name": table_name,
                        "column_name": column_name,
                    },
                    "detail": "Creating a column with a comment is not supported by compiler v1.",
                }
            )
        if int(column["ordinal_position"]) != expected_added_ordinals[index]:
            blockers.append(
                {
                    "code": "column_order_change_unsupported",
                    "object": f"{object_name}.{column_name}",
                    "object_ref": {
                        "schema_name": schema_name,
                        "table_name": table_name,
                        "column_name": column_name,
                    },
                    "detail": "New columns must be appended contiguously after existing columns in compiler v1.",
                }
            )

    for column_name in sorted(set(base_columns) - set(target_columns)):
        statements.append(
            _statement(
                kind="drop_column",
                target=f"{object_name}.{column_name}",
                object_ref={
                    "schema_name": schema_name,
                    "table_name": table_name,
                    "column_name": column_name,
                },
                sql=f"ALTER TABLE {qualified} DROP COLUMN {_quote_identifier(column_name)};",
                dependencies=[f"table:{object_name}"],
                dependency_refs=[
                    {"schema_name": schema_name, "table_name": table_name}
                ],
                reversible=False,
                risk=_risk(
                    "destructive",
                    lock_mode="ACCESS EXCLUSIVE",
                    data_loss=True,
                    detail="Drops the column and its stored values.",
                ),
                required_privileges=["OWNER"],
            )
        )

    for column_name in added_column_names:
        column = target_columns[column_name]
        preconditions: list[dict[str, Any]] = []
        severity = "safe"
        detail = "Adds a nullable column without rewriting existing rows."
        if not column["nullable"] and column.get("default") is None:
            severity = "warning"
            detail = "A required column without a default needs proof the table is empty."
            preconditions.append(
                {
                    "kind": "table_is_empty",
                    "schema_name": schema_name,
                    "table_name": table_name,
                }
            )
        statements.append(
            _statement(
                kind="add_column",
                target=f"{object_name}.{column_name}",
                object_ref={
                    "schema_name": schema_name,
                    "table_name": table_name,
                    "column_name": column_name,
                },
                sql=f"ALTER TABLE {qualified} ADD COLUMN {_column_sql(column)};",
                dependencies=[f"table:{object_name}"],
                dependency_refs=[
                    {"schema_name": schema_name, "table_name": table_name}
                ],
                reversible=True,
                risk=_risk(
                    severity,
                    lock_mode="ACCESS EXCLUSIVE",
                    possible_rewrite=False,
                    detail=detail,
                ),
                required_privileges=["OWNER"],
                preconditions=preconditions,
            )
        )

    for column_name in sorted(set(base_columns) & set(target_columns)):
        before = base_columns[column_name]
        after = target_columns[column_name]
        target_name = f"{object_name}.{column_name}"
        if before["data_type"] != after["data_type"]:
            statements.append(
                _statement(
                    kind="alter_column_type",
                    target=target_name,
                    object_ref={
                        "schema_name": schema_name,
                        "table_name": table_name,
                        "column_name": column_name,
                    },
                    sql=(
                        f"ALTER TABLE {qualified} ALTER COLUMN "
                        f"{_quote_identifier(column_name)} TYPE {after['data_type']};"
                    ),
                    dependencies=[f"column:{target_name}"],
                    dependency_refs=[
                        {
                            "schema_name": schema_name,
                            "table_name": table_name,
                            "column_name": column_name,
                        }
                    ],
                    reversible=False,
                    risk=_risk(
                        "destructive",
                        lock_mode="ACCESS EXCLUSIVE",
                        possible_rewrite=True,
                        table_scan=True,
                        data_loss=True,
                        detail="A type conversion may rewrite or change existing values and is conservatively destructive.",
                    ),
                    required_privileges=["OWNER"],
                    preconditions=[
                        {
                            "kind": "castable_values",
                            "schema_name": schema_name,
                            "table_name": table_name,
                            "column_name": column_name,
                            "target_data_type": after["data_type"],
                        }
                    ],
                )
            )
        if before["nullable"] and not after["nullable"]:
            statements.append(
                _statement(
                    kind="set_not_null",
                    target=target_name,
                    object_ref={
                        "schema_name": schema_name,
                        "table_name": table_name,
                        "column_name": column_name,
                    },
                    sql=(
                        f"ALTER TABLE {qualified} ALTER COLUMN "
                        f"{_quote_identifier(column_name)} SET NOT NULL;"
                    ),
                    dependencies=[f"column:{target_name}"],
                    dependency_refs=[
                        {
                            "schema_name": schema_name,
                            "table_name": table_name,
                            "column_name": column_name,
                        }
                    ],
                    reversible=True,
                    risk=_risk(
                        "warning",
                        lock_mode="ACCESS EXCLUSIVE",
                        table_scan=True,
                        detail="Validating NOT NULL scans existing rows and fails when NULL exists.",
                    ),
                    required_privileges=["OWNER"],
                    preconditions=[
                        {
                            "kind": "no_null_values",
                            "schema_name": schema_name,
                            "table_name": table_name,
                            "column_name": column_name,
                        }
                    ],
                )
            )
        elif not before["nullable"] and after["nullable"]:
            statements.append(
                _statement(
                    kind="drop_not_null",
                    target=target_name,
                    object_ref={
                        "schema_name": schema_name,
                        "table_name": table_name,
                        "column_name": column_name,
                    },
                    sql=(
                        f"ALTER TABLE {qualified} ALTER COLUMN "
                        f"{_quote_identifier(column_name)} DROP NOT NULL;"
                    ),
                    dependencies=[f"column:{target_name}"],
                    dependency_refs=[
                        {
                            "schema_name": schema_name,
                            "table_name": table_name,
                            "column_name": column_name,
                        }
                    ],
                    reversible=True,
                    risk=_risk(
                        "safe",
                        lock_mode="ACCESS EXCLUSIVE",
                        detail="Relaxes an existing nullability constraint.",
                    ),
                    required_privileges=["OWNER"],
                )
            )
    return statements, blockers


def _digest_plan(plan: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def compile_migration_plan(
    base_model: Mapping[str, Any], target_model: Mapping[str, Any]
) -> dict[str, Any]:
    """Compile two validated models into a deterministic immutable plan.

    The returned plan is safe to persist and hash.  A non-empty ``blockers``
    list makes ``can_dry_run`` false and suppresses every executable statement,
    preventing a partial plan from being mistaken for semantic convergence.
    """

    base = canonicalize_schema_model(base_model)
    target = canonicalize_schema_model(target_model)
    if base["postgresql_major"] != target["postgresql_major"]:
        blockers: list[dict[str, Any]] = [
            {
                "code": "postgresql_version_mismatch",
                "object": "database",
                "object_ref": {"database": "current"},
                "detail": "Base and target PostgreSQL major versions must match.",
            }
        ]
    else:
        blockers = []

    base_tables = _tables(base)
    target_tables = _tables(target)
    base_schemas = {schema["schema_name"] for schema in base["schemas"]}
    target_schemas = {schema["schema_name"] for schema in target["schemas"]}
    statements: list[dict[str, Any]] = []

    for schema_name in sorted(base_schemas - target_schemas):
        blockers.append(
            {
                "code": "schema_removal_unsupported",
                "object": schema_name,
                "object_ref": {"schema_name": schema_name},
                "detail": "Removing an existing schema is not supported by compiler v1.",
            }
        )

    for schema_name in sorted(target_schemas - base_schemas):
        statements.append(
            _statement(
                kind="create_schema",
                target=schema_name,
                object_ref={"schema_name": schema_name},
                sql=f"CREATE SCHEMA {_quote_identifier(schema_name)};",
                dependencies=[],
                dependency_refs=[],
                reversible=True,
                risk=_risk(
                    "safe",
                    lock_mode="none",
                    detail="Creates an empty schema namespace.",
                ),
                required_privileges=["CREATE"],
            )
        )

    for schema_name, table_name in sorted(set(base_tables) - set(target_tables)):
        object_name = f"{schema_name}.{table_name}"
        statements.append(
            _statement(
                kind="drop_table",
                target=object_name,
                object_ref={"schema_name": schema_name, "table_name": table_name},
                sql=f"DROP TABLE {_qualified_name(schema_name, table_name)};",
                dependencies=[f"table:{object_name}"],
                dependency_refs=[
                    {"schema_name": schema_name, "table_name": table_name}
                ],
                reversible=False,
                risk=_risk(
                    "destructive",
                    lock_mode="ACCESS EXCLUSIVE",
                    data_loss=True,
                    detail="Drops the table and all of its stored rows.",
                ),
                required_privileges=["OWNER"],
            )
        )

    for key in sorted(set(target_tables) - set(base_tables)):
        table = target_tables[key]
        object_name = f"{key[0]}.{key[1]}"
        if table.get("comment") is not None:
            blockers.append(
                {
                    "code": "table_comment_change_unsupported",
                    "object": object_name,
                    "object_ref": {
                        "schema_name": key[0],
                        "table_name": key[1],
                    },
                    "detail": "Creating a table with a comment is not supported by compiler v1.",
                }
            )
        for column in table["columns"]:
            if column.get("comment") is not None:
                blockers.append(
                    {
                        "code": "column_comment_change_unsupported",
                        "object": f"{object_name}.{column['column_name']}",
                        "object_ref": {
                            "schema_name": key[0],
                            "table_name": key[1],
                            "column_name": column["column_name"],
                        },
                        "detail": "Creating a column with a comment is not supported by compiler v1.",
                    }
                )
        statements.append(_create_table_statement(key[0], table))

    for key in sorted(set(base_tables) & set(target_tables)):
        changed, table_blockers = _compile_table_changes(
            key[0], key[1], base_tables[key], target_tables[key]
        )
        statements.extend(changed)
        blockers.extend(table_blockers)

    proposed_statements = statements if blockers else []
    executable_statements = [] if blockers else statements
    risk_summary = {
        severity: sum(
            statement["risk"]["severity"] == severity for statement in statements
        )
        for severity in ("safe", "warning", "destructive")
    }
    plan: dict[str, Any] = {
        "compiler_version": COMPILER_VERSION,
        "postgresql_major": target["postgresql_major"],
        "base_digest": schema_model_digest(base),
        "target_digest": schema_model_digest(target),
        "statements": executable_statements,
        "proposed_statements": proposed_statements,
        "blockers": blockers,
        "risk_summary": risk_summary,
        "requires_destructive_confirmation": risk_summary["destructive"] > 0,
        "can_dry_run": not blockers,
    }
    plan["plan_digest"] = _digest_plan(plan)
    return plan
