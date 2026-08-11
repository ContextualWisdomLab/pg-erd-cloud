"""Execute one immutable v1 plan inside an already isolated PostgreSQL sandbox.

Provisioning, dependency materialization, network isolation, and sandbox cleanup
remain worker responsibilities.  This module accepts neither a DSN nor browser
SQL.  It verifies the persisted plan digest, checks the disposable server and
materialized base, executes the compiler-owned transactional statements, and
requires a fresh strict snapshot to converge on the planned target digest.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.forward.migration_plan import COMPILER_VERSION, verify_migration_plan_digest
from app.forward.schema_model import SchemaModelValidationError, schema_model_digest
from app.forward.snapshot_adapter import snapshot_to_schema_model

MAX_DRY_RUN_STATEMENTS = 1_000
MAX_DRY_RUN_SQL_BYTES = 262_144
MIN_TIMEOUT_MS = 1
MAX_LOCK_TIMEOUT_MS = 60_000
MAX_STATEMENT_TIMEOUT_MS = 300_000

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_SUPPORTED_KINDS = frozenset(
    {
        "create_schema",
        "create_table",
        "drop_table",
        "add_column",
        "drop_column",
        "alter_column_type",
        "set_not_null",
        "drop_not_null",
    }
)
_PLAN_FIELDS = frozenset(
    {
        "compiler_version",
        "snapshot_contract_version",
        "postgresql_major",
        "base_digest",
        "target_digest",
        "statements",
        "proposed_statements",
        "blockers",
        "risk_summary",
        "requires_destructive_confirmation",
        "can_dry_run",
        "plan_digest",
    }
)
_STATEMENT_FIELDS = frozenset(
    {
        "kind",
        "target",
        "object_ref",
        "sql",
        "transactional",
        "dependencies",
        "dependency_refs",
        "reversible",
        "risk",
        "required_privileges",
        "preconditions",
    }
)


class _PreparedStatement(Protocol):
    async def fetch(self) -> Sequence[object]: ...


class _Transaction(Protocol):
    async def start(self) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class IsolatedPostgresConnection(Protocol):
    """Minimum asyncpg-compatible surface used by the sandbox executor."""

    async def fetchval(self, query: str) -> object: ...

    def transaction(self) -> _Transaction: ...

    async def execute(self, query: str, value: str) -> str: ...

    async def prepare(self, query: str) -> _PreparedStatement: ...


SnapshotCapture = Callable[
    [IsolatedPostgresConnection], Awaitable[Mapping[str, Any]]
]


class IsolatedDryRunContractError(ValueError):
    """Raised when isolated execution cannot produce trusted convergence."""


@dataclass(frozen=True)
class _ExecutablePlan:
    postgresql_major: int
    base_digest: str
    target_digest: str
    statements: tuple[str, ...]


def _require_timeout(value: int, *, maximum: int, name: str) -> None:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < MIN_TIMEOUT_MS
        or value > maximum
    ):
        raise IsolatedDryRunContractError(f"{name} is outside the allowed range")


def _require_digest(value: object, *, name: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise IsolatedDryRunContractError(f"{name} is invalid")
    return value


def _validated_plan(
    plan: Mapping[str, Any], expected_plan_digest: str
) -> _ExecutablePlan:
    expected_digest = _require_digest(
        expected_plan_digest, name="expected plan digest"
    )
    if not verify_migration_plan_digest(plan, expected_digest):
        raise IsolatedDryRunContractError("migration plan digest is invalid")
    if set(plan) != _PLAN_FIELDS:
        raise IsolatedDryRunContractError("migration plan contract is invalid")
    if plan.get("compiler_version") != COMPILER_VERSION:
        raise IsolatedDryRunContractError("migration plan compiler is unsupported")
    if plan.get("can_dry_run") is not True or plan.get("blockers") != []:
        raise IsolatedDryRunContractError("migration plan is not dry-runnable")

    postgresql_major = plan.get("postgresql_major")
    if (
        not isinstance(postgresql_major, int)
        or isinstance(postgresql_major, bool)
        or postgresql_major < 14
        or postgresql_major > 18
    ):
        raise IsolatedDryRunContractError("planned PostgreSQL major is invalid")
    base_digest = _require_digest(plan.get("base_digest"), name="base digest")
    target_digest = _require_digest(plan.get("target_digest"), name="target digest")
    if plan.get("proposed_statements") != []:
        raise IsolatedDryRunContractError("migration plan contract is invalid")

    raw_statements = plan.get("statements")
    if (
        not isinstance(raw_statements, list)
        or len(raw_statements) > MAX_DRY_RUN_STATEMENTS
    ):
        raise IsolatedDryRunContractError("migration plan statements are invalid")
    statements: list[str] = []
    for statement in raw_statements:
        if not isinstance(statement, Mapping):
            raise IsolatedDryRunContractError("migration plan statement is invalid")
        if set(statement) != _STATEMENT_FIELDS:
            raise IsolatedDryRunContractError(
                "migration plan statement contract is invalid"
            )
        if statement.get("kind") not in _SUPPORTED_KINDS:
            raise IsolatedDryRunContractError(
                "migration plan statement kind is unsupported"
            )
        if statement.get("transactional") is not True:
            raise IsolatedDryRunContractError(
                "migration plan contains a non-transactional statement"
            )
        sql = statement.get("sql")
        if (
            not isinstance(sql, str)
            or not sql
            or len(sql.encode("utf-8")) > MAX_DRY_RUN_SQL_BYTES
        ):
            raise IsolatedDryRunContractError("migration plan statement SQL is invalid")
        statements.append(sql)
    if not statements and base_digest != target_digest:
        raise IsolatedDryRunContractError("migration plan contract is invalid")
    return _ExecutablePlan(
        postgresql_major=postgresql_major,
        base_digest=base_digest,
        target_digest=target_digest,
        statements=tuple(statements),
    )


def _captured_digest(snapshot: Mapping[str, Any]) -> str:
    try:
        model = snapshot_to_schema_model(snapshot)
    except (SchemaModelValidationError, TypeError, ValueError):
        raise IsolatedDryRunContractError(
            "isolated sandbox snapshot is invalid"
        ) from None
    return schema_model_digest(model)


async def _capture_digest(
    connection: IsolatedPostgresConnection, capture_snapshot: SnapshotCapture
) -> str:
    try:
        snapshot = await capture_snapshot(connection)
    except BaseException as exc:
        if not isinstance(exc, Exception):
            raise
        raise IsolatedDryRunContractError(
            "isolated sandbox snapshot capture failed"
        ) from None
    if not isinstance(snapshot, Mapping):
        raise IsolatedDryRunContractError("isolated sandbox snapshot is invalid")
    return _captured_digest(snapshot)


async def execute_isolated_dry_run(
    connection: IsolatedPostgresConnection,
    plan: Mapping[str, Any],
    *,
    expected_plan_digest: str,
    capture_snapshot: SnapshotCapture,
    lock_timeout_ms: int = 1_000,
    statement_timeout_ms: int = 30_000,
) -> dict[str, object]:
    """Execute a verified plan on a disposable, pre-materialized sandbox.

    The caller must prove the connection is disposable and isolated and must
    destroy or sanitize it after this function returns or raises.  Snapshot
    capture is worker-owned and must introspect this sandbox, never the live
    target or application metadata database.
    """

    executable = _validated_plan(plan, expected_plan_digest)
    _require_timeout(
        lock_timeout_ms, maximum=MAX_LOCK_TIMEOUT_MS, name="lock timeout"
    )
    _require_timeout(
        statement_timeout_ms,
        maximum=MAX_STATEMENT_TIMEOUT_MS,
        name="statement timeout",
    )

    try:
        server_version_num = await connection.fetchval(
            "SELECT pg_catalog.current_setting('server_version_num')::integer"
        )
        if (
            not isinstance(server_version_num, int)
            or isinstance(server_version_num, bool)
            or server_version_num // 10_000 != executable.postgresql_major
        ):
            raise IsolatedDryRunContractError(
                "isolated PostgreSQL major version mismatch"
            )
    except IsolatedDryRunContractError:
        raise
    except BaseException as exc:
        if not isinstance(exc, Exception):
            raise
        raise IsolatedDryRunContractError(
            "isolated PostgreSQL version check failed"
        ) from None

    observed_base_digest = await _capture_digest(connection, capture_snapshot)
    if observed_base_digest != executable.base_digest:
        raise IsolatedDryRunContractError(
            "isolated sandbox does not match the planned base"
        )

    transaction_started = False
    try:
        transaction = connection.transaction()
        await transaction.start()
        transaction_started = True
        await connection.execute(
            "SELECT pg_catalog.set_config('lock_timeout', $1, true)",
            str(lock_timeout_ms),
        )
        await connection.execute(
            "SELECT pg_catalog.set_config('statement_timeout', $1, true)",
            str(statement_timeout_ms),
        )
        for sql in executable.statements:
            prepared = await connection.prepare(sql)
            await prepared.fetch()
        await transaction.commit()
    except BaseException as exc:
        if transaction_started:
            try:
                await transaction.rollback()
            except Exception:
                # Preserve the fixed primary failure and never driver detail.
                pass
        if not isinstance(exc, Exception):
            raise
        raise IsolatedDryRunContractError(
            "isolated dry-run statement failed"
        ) from None

    observed_target_digest = await _capture_digest(connection, capture_snapshot)
    if observed_target_digest != executable.target_digest:
        raise IsolatedDryRunContractError(
            "isolated dry run did not converge"
        ) from None
    return {
        "postgresql_major": executable.postgresql_major,
        "statement_count": len(executable.statements),
        "base_digest": observed_base_digest,
        "target_digest": observed_target_digest,
        "converged": True,
    }
