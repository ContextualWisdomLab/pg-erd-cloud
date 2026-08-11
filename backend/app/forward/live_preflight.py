"""Compile and execute bounded, read-only live-target preconditions.

This module is an execution-neutral primitive for the planned dry-run worker.
It consumes only the structured preconditions already bound into an immutable
migration plan.  It neither accepts arbitrary SQL nor owns target credentials,
fresh snapshot capture, run transitions, or apply authority.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import asyncpg

from app.forward.schema_model import (
    SchemaModelValidationError,
    canonicalize_data_type,
    schema_model_digest,
)
from app.forward.snapshot_adapter import snapshot_to_schema_model

MAX_LIVE_PREFLIGHT_QUERIES = 1000
MAX_STATEMENT_TIMEOUT_MS = 60_000
_SHA256_HEX_RE = re.compile(r"[0-9a-f]{64}")


class LivePreflightContractError(ValueError):
    """Reject malformed plans or incomplete live-preflight evidence."""


@dataclass(frozen=True)
class LivePreflightQuery:
    """One server-compiled read query bound to a plan precondition position."""

    statement_index: int
    precondition_index: int
    kind: str
    sql: str


def compare_live_preflight_snapshot(
    plan: Mapping[str, object], snapshot: Mapping[str, Any]
) -> dict[str, object]:
    """Compare one strictly adapted target snapshot with the planned base.

    The caller owns fresh capture, connection authorization, and durable state
    transitions. This pure boundary only rejects malformed inputs and returns
    the canonical observed digest plus an explicit match result.
    """

    expected_digest = plan.get("base_digest")
    if not isinstance(expected_digest, str) or _SHA256_HEX_RE.fullmatch(
        expected_digest
    ) is None:
        raise LivePreflightContractError("live preflight base digest is invalid")
    try:
        observed_digest = schema_model_digest(snapshot_to_schema_model(snapshot))
    except SchemaModelValidationError as err:
        raise LivePreflightContractError(str(err)) from None
    return {
        "observed_base_digest": observed_digest,
        "matches_plan_base": observed_digest == expected_digest,
    }


def _quote_identifier(identifier: object) -> str:
    if not isinstance(identifier, str):
        raise LivePreflightContractError("live preflight identifier must be text")
    if not identifier or "\x00" in identifier:
        raise LivePreflightContractError("live preflight identifier is invalid")
    if len(identifier.encode("utf-8")) > 63:
        raise LivePreflightContractError("live preflight identifier is too large")
    return '"' + identifier.replace('"', '""') + '"'


def _precondition_fields(
    value: Mapping[str, object], allowed: set[str]
) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise LivePreflightContractError(
            f"live preflight precondition contains unrecognized field {sorted(unknown)[0]!r}"
        )
    missing = allowed - set(value)
    if missing:
        raise LivePreflightContractError(
            f"live preflight precondition is missing field {sorted(missing)[0]!r}"
        )


def _compile_precondition(
    precondition: Mapping[str, object],
    *,
    statement_index: int,
    precondition_index: int,
) -> LivePreflightQuery:
    kind = precondition.get("kind")
    if not isinstance(kind, str):
        raise LivePreflightContractError("live preflight precondition kind is invalid")

    common = {"kind", "schema_name", "table_name"}
    if kind == "table_is_empty":
        _precondition_fields(precondition, common)
        table = (
            f"{_quote_identifier(precondition['schema_name'])}."
            f"{_quote_identifier(precondition['table_name'])}"
        )
        sql = f"SELECT NOT EXISTS (SELECT 1 FROM {table} LIMIT 1)"
    elif kind == "no_null_values":
        _precondition_fields(precondition, common | {"column_name"})
        table = (
            f"{_quote_identifier(precondition['schema_name'])}."
            f"{_quote_identifier(precondition['table_name'])}"
        )
        column = _quote_identifier(precondition["column_name"])
        sql = (
            f"SELECT NOT EXISTS (SELECT 1 FROM {table} "
            f"WHERE {column} IS NULL LIMIT 1)"
        )
    elif kind == "castable_values":
        _precondition_fields(
            precondition, common | {"column_name", "target_data_type"}
        )
        table = (
            f"{_quote_identifier(precondition['schema_name'])}."
            f"{_quote_identifier(precondition['table_name'])}"
        )
        column = _quote_identifier(precondition["column_name"])
        try:
            target_data_type = canonicalize_data_type(
                precondition["target_data_type"],
                "live_preflight.target_data_type",
            )
        except SchemaModelValidationError as err:
            raise LivePreflightContractError(str(err)) from None
        sql = (
            f"SELECT COALESCE(bool_and(({column})::{target_data_type} IS NOT NULL), TRUE) "
            f"FROM {table} WHERE {column} IS NOT NULL"
        )
    else:
        raise LivePreflightContractError(
            f"unsupported live preflight precondition {kind!r}"
        )

    return LivePreflightQuery(
        statement_index=statement_index,
        precondition_index=precondition_index,
        kind=kind,
        sql=sql,
    )


def compile_live_preflight_queries(
    plan: Mapping[str, object],
) -> tuple[LivePreflightQuery, ...]:
    """Compile only recognized structured preconditions into bounded reads."""

    blockers = plan.get("blockers")
    statements = plan.get("statements")
    if plan.get("can_dry_run") is not True or blockers != []:
        raise LivePreflightContractError("migration plan cannot enter live preflight")
    if not isinstance(statements, list):
        raise LivePreflightContractError("migration plan statements must be a list")

    queries: list[LivePreflightQuery] = []
    for statement_index, statement in enumerate(statements):
        if not isinstance(statement, Mapping):
            raise LivePreflightContractError("migration plan statement must be an object")
        preconditions = statement.get("preconditions")
        if not isinstance(preconditions, list):
            raise LivePreflightContractError(
                "migration plan preconditions must be a list"
            )
        for precondition_index, precondition in enumerate(preconditions):
            if len(queries) >= MAX_LIVE_PREFLIGHT_QUERIES:
                raise LivePreflightContractError(
                    "live preflight contains too many queries"
                )
            if not isinstance(precondition, Mapping):
                raise LivePreflightContractError(
                    "live preflight precondition must be an object"
                )
            queries.append(
                _compile_precondition(
                    precondition,
                    statement_index=statement_index,
                    precondition_index=precondition_index,
                )
            )
    return tuple(queries)


async def execute_live_preflight(
    connection: asyncpg.Connection,
    plan: Mapping[str, object],
    *,
    statement_timeout_ms: int = 5000,
) -> dict[str, Any]:
    """Execute compiled checks in one bounded read-only target snapshot."""

    if (
        not isinstance(statement_timeout_ms, int)
        or isinstance(statement_timeout_ms, bool)
        or not 1 <= statement_timeout_ms <= MAX_STATEMENT_TIMEOUT_MS
    ):
        raise LivePreflightContractError(
            "live preflight statement timeout is invalid"
        )
    queries = compile_live_preflight_queries(plan)
    transaction = connection.transaction(isolation="repeatable_read", readonly=True)
    await transaction.start()
    try:
        await connection.execute(
            f"SET LOCAL statement_timeout = '{statement_timeout_ms}ms'"
        )
        client_timeout = statement_timeout_ms / 1000 + 1
        checks: list[dict[str, object]] = []
        for query in queries:
            result = await connection.fetchval(query.sql, timeout=client_timeout)
            if not isinstance(result, bool):
                raise LivePreflightContractError(
                    "live preflight database result is not boolean"
                )
            checks.append(
                {
                    "statement_index": query.statement_index,
                    "precondition_index": query.precondition_index,
                    "kind": query.kind,
                    "passed": result,
                }
            )
    except BaseException as err:
        await transaction.rollback()
        if isinstance(
            err,
            (
                LivePreflightContractError,
                asyncio.CancelledError,
                KeyboardInterrupt,
                SystemExit,
            ),
        ):
            raise
        raise LivePreflightContractError("live preflight query failed") from None
    await transaction.commit()
    return {"passed": all(bool(item["passed"]) for item in checks), "checks": checks}
