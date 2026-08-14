"""Compile immutable migration plans into deterministic table-lock targets.

This module is an execution-neutral input boundary for the planned apply
executor. It consumes structured statement metadata, never parses rendered SQL,
and does not connect to PostgreSQL, acquire locks, dispatch work, or execute DDL.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

MAX_APPLY_LOCK_STATEMENTS = 1000
MAX_APPLY_LOCK_TARGETS = 1000

_EXISTING_TABLE_STATEMENT_KINDS = frozenset(
    {
        "add_column",
        "alter_column_type",
        "drop_column",
        "drop_not_null",
        "drop_table",
        "set_not_null",
    }
)
_NEW_OBJECT_STATEMENT_KINDS = frozenset({"create_schema", "create_table"})
_SUPPORTED_STATEMENT_KINDS = (
    _EXISTING_TABLE_STATEMENT_KINDS | _NEW_OBJECT_STATEMENT_KINDS
)


class ApplyLockPlanContractError(ValueError):
    """Reject a plan that cannot safely produce deterministic lock targets."""


@dataclass(frozen=True)
class ApplyLockTarget:
    """One existing PostgreSQL table that a future executor must lock."""

    schema_name: str
    table_name: str
    sql: str


def _quote_identifier(identifier: object) -> str:
    """Return one bounded PostgreSQL delimited identifier."""

    if not isinstance(identifier, str):
        raise ApplyLockPlanContractError("apply lock identifier must be text")
    if not identifier or "\x00" in identifier:
        raise ApplyLockPlanContractError("apply lock identifier is invalid")
    if len(identifier.encode("utf-8")) > 63:
        raise ApplyLockPlanContractError("apply lock identifier is too large")
    return '"' + identifier.replace('"', '""') + '"'


def _object_table_ref(statement: Mapping[str, object]) -> tuple[str, str]:
    """Extract and validate one structured schema/table reference."""

    object_ref = statement.get("object_ref")
    if not isinstance(object_ref, Mapping):
        raise ApplyLockPlanContractError("apply lock object reference is invalid")
    schema_name = object_ref.get("schema_name")
    table_name = object_ref.get("table_name")
    _quote_identifier(schema_name)
    _quote_identifier(table_name)
    return cast(str, schema_name), cast(str, table_name)


def _lock_mode(statement: Mapping[str, object]) -> object:
    """Read the reviewed risk lock mode without consulting rendered SQL."""

    risk = statement.get("risk")
    if not isinstance(risk, Mapping):
        raise ApplyLockPlanContractError("apply lock risk metadata is invalid")
    return risk.get("lock_mode")


def compile_apply_lock_targets(
    plan: Mapping[str, object],
) -> tuple[ApplyLockTarget, ...]:
    """Return sorted unique existing-table locks for compiler-v1 statements.

    New schemas and tables have no pre-existing relation to lock. Every
    existing-table operation must remain transactional and declare the
    compiler-v1 ``ACCESS EXCLUSIVE`` risk mode. Unknown statement kinds fail
    closed so a future compiler capability cannot silently bypass lock planning.
    """

    if plan.get("can_dry_run") is not True or plan.get("blockers") != []:
        raise ApplyLockPlanContractError(
            "migration plan cannot enter apply lock planning"
        )
    statements = plan.get("statements")
    if not isinstance(statements, list):
        raise ApplyLockPlanContractError("migration plan statements must be a list")
    if len(statements) > MAX_APPLY_LOCK_STATEMENTS:
        raise ApplyLockPlanContractError(
            "apply lock plan contains too many statements"
        )

    targets: set[tuple[str, str]] = set()
    for statement in statements:
        if not isinstance(statement, Mapping):
            raise ApplyLockPlanContractError(
                "migration plan statement must be an object"
            )
        kind = statement.get("kind")
        if not isinstance(kind, str) or kind not in _SUPPORTED_STATEMENT_KINDS:
            raise ApplyLockPlanContractError(
                "unsupported apply statement kind"
            )
        if statement.get("transactional") is not True:
            raise ApplyLockPlanContractError(
                "apply plan statement must be transactional"
            )

        if kind == "create_schema":
            if _lock_mode(statement) != "none":
                raise ApplyLockPlanContractError("apply lock mode is invalid")
            object_ref = statement.get("object_ref")
            if not isinstance(object_ref, Mapping):
                raise ApplyLockPlanContractError(
                    "apply lock object reference is invalid"
                )
            _quote_identifier(object_ref.get("schema_name"))
            continue

        schema_name, table_name = _object_table_ref(statement)
        if _lock_mode(statement) != "ACCESS EXCLUSIVE":
            raise ApplyLockPlanContractError("apply lock mode is invalid")
        if kind == "create_table":
            continue
        targets.add((schema_name, table_name))
        if len(targets) > MAX_APPLY_LOCK_TARGETS:
            raise ApplyLockPlanContractError(
                "apply lock plan contains too many targets"
            )

    return tuple(
        ApplyLockTarget(
            schema_name=schema_name,
            table_name=table_name,
            sql=(
                f"LOCK TABLE {_quote_identifier(schema_name)}."
                f"{_quote_identifier(table_name)} IN ACCESS EXCLUSIVE MODE"
            ),
        )
        for schema_name, table_name in sorted(targets)
    )
