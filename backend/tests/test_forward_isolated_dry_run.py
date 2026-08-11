from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping
from typing import Any

import pytest

from app.forward.isolated_dry_run import (
    IsolatedDryRunContractError,
    execute_isolated_dry_run,
)
from app.forward.migration_plan import compile_migration_plan


def _models() -> tuple[dict[str, Any], dict[str, Any]]:
    base = {"format_version": 1, "postgresql_major": 18, "schemas": []}
    target = {
        "format_version": 1,
        "postgresql_major": 18,
        "schemas": [
            {
                "schema_name": "Sales Data",
                "tables": [
                    {
                        "table_name": 'Order "Item"',
                        "columns": [
                            {
                                "column_name": "Item ID",
                                "data_type": "bigint",
                                "nullable": True,
                                "ordinal_position": 1,
                            }
                        ],
                    }
                ],
            }
        ],
    }
    return base, target


def _snapshots() -> tuple[dict[str, Any], dict[str, Any]]:
    empty = {
        "snapshot_contract_version": 1,
        "server_version_num": 180002,
        "schemas": [],
        "relations": [],
        "columns": [],
        "pk_columns": [],
        "constraints": [],
        "fk_edges": [],
        "indexes": [],
    }
    target = {
        **empty,
        "schemas": [{"schema_oid": 11, "schema_name": "Sales Data"}],
        "relations": [
            {
                "relation_oid": 42,
                "schema_name": "Sales Data",
                "relation_name": 'Order "Item"',
                "relation_kind": "r",
            }
        ],
        "columns": [
            {
                "relation_oid": 42,
                "column_name": "Item ID",
                "data_type": "bigint",
                "is_not_null": False,
                "column_position": 1,
            }
        ],
    }
    return empty, target


def _resign(plan: Mapping[str, Any]) -> dict[str, Any]:
    signed = dict(plan)
    signed.pop("plan_digest", None)
    digest = hashlib.sha256(
        json.dumps(
            signed, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()
    signed["plan_digest"] = digest
    return signed


class _PreparedStatement:
    def __init__(self, connection: "_Connection", sql: str) -> None:
        self.connection = connection
        self.sql = sql

    async def fetch(self) -> list[object]:
        self.connection.calls.append(("prepared_fetch", self.sql))
        if self.connection.fail_statement == self.sql:
            raise RuntimeError("driver detail containing a secret")
        return []


class _Transaction:
    def __init__(self, connection: "_Connection") -> None:
        self.connection = connection

    async def start(self) -> None:
        self.connection.calls.append(("start",))
        self.connection.transaction_started = True

    async def commit(self) -> None:
        self.connection.calls.append(("commit",))
        self.connection.transaction_started = False

    async def rollback(self) -> None:
        self.connection.calls.append(("rollback",))
        self.connection.transaction_started = False


class _Connection:
    def __init__(self, *, major: int = 18) -> None:
        self.major = major
        self.calls: list[tuple[object, ...]] = []
        self.fail_statement: str | None = None
        self.transaction_started = False

    async def fetchval(self, query: str) -> int:
        self.calls.append(("fetchval", query))
        return self.major * 10_000

    def transaction(self) -> _Transaction:
        self.calls.append(("transaction",))
        return _Transaction(self)

    async def execute(self, query: str, value: str) -> str:
        self.calls.append(("execute", query, value))
        return "SELECT 1"

    async def prepare(self, sql: str) -> _PreparedStatement:
        self.calls.append(("prepare", sql))
        return _PreparedStatement(self, sql)


@pytest.mark.asyncio
async def test_executes_exact_signed_plan_and_requires_semantic_convergence() -> None:
    base, target = _models()
    plan = compile_migration_plan(base, target)
    connection = _Connection()
    snapshots = iter(_snapshots())

    async def capture(_connection: _Connection) -> Mapping[str, Any]:
        return next(snapshots)

    evidence = await execute_isolated_dry_run(
        connection,
        plan,
        expected_plan_digest=plan["plan_digest"],
        capture_snapshot=capture,
        lock_timeout_ms=750,
        statement_timeout_ms=2_500,
    )

    assert evidence == {
        "postgresql_major": 18,
        "statement_count": 2,
        "base_digest": plan["base_digest"],
        "target_digest": plan["target_digest"],
        "converged": True,
    }
    assert connection.calls == [
        (
            "fetchval",
            "SELECT pg_catalog.current_setting('server_version_num')::integer",
        ),
        ("transaction",),
        ("start",),
        (
            "execute",
            "SELECT pg_catalog.set_config('lock_timeout', $1, true)",
            "750",
        ),
        (
            "execute",
            "SELECT pg_catalog.set_config('statement_timeout', $1, true)",
            "2500",
        ),
        ("prepare", plan["statements"][0]["sql"]),
        ("prepared_fetch", plan["statements"][0]["sql"]),
        ("prepare", plan["statements"][1]["sql"]),
        ("prepared_fetch", plan["statements"][1]["sql"]),
        ("commit",),
    ]


@pytest.mark.asyncio
async def test_rejects_wrong_server_or_tampered_plan_before_transaction() -> None:
    base, target = _models()
    plan = compile_migration_plan(base, target)
    base_snapshot, _target_snapshot = _snapshots()
    wrong_server = _Connection(major=17)

    async def capture(_connection: _Connection) -> Mapping[str, Any]:
        return base_snapshot

    with pytest.raises(IsolatedDryRunContractError, match="major version mismatch"):
        await execute_isolated_dry_run(
            wrong_server,
            plan,
            expected_plan_digest=plan["plan_digest"],
            capture_snapshot=capture,
        )
    assert all(call[0] != "transaction" for call in wrong_server.calls)

    tampered = {**plan, "target_digest": "f" * 64}
    untouched = _Connection()
    with pytest.raises(IsolatedDryRunContractError, match="digest is invalid"):
        await execute_isolated_dry_run(
            untouched,
            tampered,
            expected_plan_digest=plan["plan_digest"],
            capture_snapshot=capture,
        )
    assert untouched.calls == []


@pytest.mark.asyncio
async def test_rolls_back_and_masks_statement_failure() -> None:
    base, target = _models()
    plan = compile_migration_plan(base, target)
    base_snapshot, _target_snapshot = _snapshots()
    connection = _Connection()
    connection.fail_statement = plan["statements"][1]["sql"]

    async def capture(_connection: _Connection) -> Mapping[str, Any]:
        return base_snapshot

    with pytest.raises(IsolatedDryRunContractError) as captured:
        await execute_isolated_dry_run(
            connection,
            plan,
            expected_plan_digest=plan["plan_digest"],
            capture_snapshot=capture,
        )

    assert str(captured.value) == "isolated dry-run statement failed"
    assert captured.value.__cause__ is None
    assert ("rollback",) in connection.calls
    assert ("commit",) not in connection.calls


@pytest.mark.asyncio
async def test_propagates_cancellation_after_rollback() -> None:
    base, target = _models()
    plan = compile_migration_plan(base, target)
    base_snapshot, _target_snapshot = _snapshots()
    connection = _Connection()

    async def capture(_connection: _Connection) -> Mapping[str, Any]:
        return base_snapshot

    async def cancelled_fetch() -> list[object]:
        raise asyncio.CancelledError

    statement = await connection.prepare(plan["statements"][0]["sql"])
    statement.fetch = cancelled_fetch  # type: ignore[method-assign]

    async def prepare(_sql: str) -> _PreparedStatement:
        return statement

    connection.prepare = prepare  # type: ignore[method-assign]
    with pytest.raises(asyncio.CancelledError):
        await execute_isolated_dry_run(
            connection,
            plan,
            expected_plan_digest=plan["plan_digest"],
            capture_snapshot=capture,
        )
    assert ("rollback",) in connection.calls


@pytest.mark.asyncio
async def test_rejects_non_transactional_or_nonconvergent_plan() -> None:
    base, target = _models()
    plan = compile_migration_plan(base, target)
    base_snapshot, _target_snapshot = _snapshots()

    async def base_capture(_connection: _Connection) -> Mapping[str, Any]:
        return base_snapshot

    non_transactional = _resign({
        **plan,
        "statements": [{**plan["statements"][0], "transactional": False}],
    })
    with pytest.raises(IsolatedDryRunContractError, match="non-transactional"):
        await execute_isolated_dry_run(
            _Connection(),
            non_transactional,
            expected_plan_digest=non_transactional["plan_digest"],
            capture_snapshot=base_capture,
        )

    snapshots = iter((base_snapshot, base_snapshot))

    async def unchanged(_connection: _Connection) -> Mapping[str, Any]:
        return next(snapshots)

    with pytest.raises(IsolatedDryRunContractError) as captured:
        await execute_isolated_dry_run(
            _Connection(),
            plan,
            expected_plan_digest=plan["plan_digest"],
            capture_snapshot=unchanged,
        )
    assert str(captured.value) == "isolated dry run did not converge"
    assert captured.value.__cause__ is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"compiler_version": "future"}, "compiler is unsupported"),
        ({"can_dry_run": False}, "not dry-runnable"),
        ({"blockers": [{"code": "blocked"}]}, "not dry-runnable"),
        ({"postgresql_major": True}, "major is invalid"),
        ({"postgresql_major": 13}, "major is invalid"),
        ({"postgresql_major": 19}, "major is invalid"),
        ({"base_digest": "A" * 64}, "base digest is invalid"),
        ({"target_digest": None}, "target digest is invalid"),
        ({"statements": None}, "statements are invalid"),
        ({"statements": ["invalid"]}, "statement is invalid"),
    ],
)
async def test_rejects_resigned_invalid_plan_shapes(
    mutation: Mapping[str, Any], message: str
) -> None:
    base, target = _models()
    base_snapshot, _target_snapshot = _snapshots()
    invalid = _resign({**compile_migration_plan(base, target), **mutation})

    async def capture(_connection: _Connection) -> Mapping[str, Any]:
        return base_snapshot

    with pytest.raises(IsolatedDryRunContractError, match=message):
        await execute_isolated_dry_run(
            _Connection(),
            invalid,
            expected_plan_digest=invalid["plan_digest"],
            capture_snapshot=capture,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        {"unexpected": "authority drift"},
        {"statements": []},
        {"proposed_statements": [{"kind": "create_schema"}]},
    ],
)
async def test_rejects_resigned_noncanonical_executable_plan(
    mutation: Mapping[str, Any],
) -> None:
    base, target = _models()
    base_snapshot, _target_snapshot = _snapshots()
    invalid = _resign({**compile_migration_plan(base, target), **mutation})

    async def capture(_connection: _Connection) -> Mapping[str, Any]:
        return base_snapshot

    with pytest.raises(IsolatedDryRunContractError, match="plan contract"):
        await execute_isolated_dry_run(
            _Connection(),
            invalid,
            expected_plan_digest=invalid["plan_digest"],
            capture_snapshot=capture,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("statement_mutation", "message"),
    [
        ({"kind": "future_operation"}, "kind is unsupported"),
        ({"transactional": False}, "non-transactional"),
        ({"sql": None}, "SQL is invalid"),
        ({"sql": ""}, "SQL is invalid"),
        ({"sql": "x" * 262_145}, "SQL is invalid"),
    ],
)
async def test_rejects_resigned_invalid_statement_shapes(
    statement_mutation: Mapping[str, Any], message: str
) -> None:
    base, target = _models()
    base_snapshot, _target_snapshot = _snapshots()
    plan = compile_migration_plan(base, target)
    invalid = _resign(
        {
            **plan,
            "statements": [{**plan["statements"][0], **statement_mutation}],
        }
    )

    async def capture(_connection: _Connection) -> Mapping[str, Any]:
        return base_snapshot

    with pytest.raises(IsolatedDryRunContractError, match=message):
        await execute_isolated_dry_run(
            _Connection(),
            invalid,
            expected_plan_digest=invalid["plan_digest"],
            capture_snapshot=capture,
        )


@pytest.mark.asyncio
async def test_rejects_resigned_statement_with_unknown_field() -> None:
    base, target = _models()
    base_snapshot, _target_snapshot = _snapshots()
    plan = compile_migration_plan(base, target)
    invalid = _resign(
        {
            **plan,
            "statements": [{**plan["statements"][0], "raw_sql": "hidden"}],
        }
    )

    async def capture(_connection: _Connection) -> Mapping[str, Any]:
        return base_snapshot

    with pytest.raises(IsolatedDryRunContractError, match="statement contract"):
        await execute_isolated_dry_run(
            _Connection(),
            invalid,
            expected_plan_digest=invalid["plan_digest"],
            capture_snapshot=capture,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("lock_timeout", "statement_timeout"),
    [(True, 1), (0, 1), (60_001, 1), (1, False), (1, 0), (1, 300_001)],
)
async def test_rejects_timeout_bounds(
    lock_timeout: int, statement_timeout: int
) -> None:
    base, target = _models()
    base_snapshot, _target_snapshot = _snapshots()
    plan = compile_migration_plan(base, target)

    async def capture(_connection: _Connection) -> Mapping[str, Any]:
        return base_snapshot

    with pytest.raises(IsolatedDryRunContractError, match="timeout"):
        await execute_isolated_dry_run(
            _Connection(),
            plan,
            expected_plan_digest=plan["plan_digest"],
            capture_snapshot=capture,
            lock_timeout_ms=lock_timeout,
            statement_timeout_ms=statement_timeout,
        )


@pytest.mark.asyncio
async def test_rejects_invalid_expected_digest_and_oversized_statement_list() -> None:
    base, target = _models()
    base_snapshot, _target_snapshot = _snapshots()
    plan = compile_migration_plan(base, target)

    async def capture(_connection: _Connection) -> Mapping[str, Any]:
        return base_snapshot

    with pytest.raises(IsolatedDryRunContractError, match="expected plan digest"):
        await execute_isolated_dry_run(
            _Connection(),
            plan,
            expected_plan_digest="A" * 64,
            capture_snapshot=capture,
        )

    oversized = _resign({**plan, "statements": [plan["statements"][0]] * 1_001})
    with pytest.raises(IsolatedDryRunContractError, match="statements are invalid"):
        await execute_isolated_dry_run(
            _Connection(),
            oversized,
            expected_plan_digest=oversized["plan_digest"],
            capture_snapshot=capture,
        )


@pytest.mark.asyncio
async def test_rejects_capture_failures_invalid_snapshots_and_wrong_base() -> None:
    base, target = _models()
    base_snapshot, _target_snapshot = _snapshots()
    plan = compile_migration_plan(base, target)

    async def failed(_connection: _Connection) -> Mapping[str, Any]:
        raise RuntimeError("secret driver detail")

    with pytest.raises(IsolatedDryRunContractError) as captured:
        await execute_isolated_dry_run(
            _Connection(),
            plan,
            expected_plan_digest=plan["plan_digest"],
            capture_snapshot=failed,
        )
    assert str(captured.value) == "isolated sandbox snapshot capture failed"
    assert captured.value.__cause__ is None

    async def not_mapping(_connection: _Connection) -> Any:
        return []

    with pytest.raises(IsolatedDryRunContractError, match="snapshot is invalid"):
        await execute_isolated_dry_run(
            _Connection(),
            plan,
            expected_plan_digest=plan["plan_digest"],
            capture_snapshot=not_mapping,
        )

    invalid_snapshot = {**base_snapshot, "snapshot_contract_version": 999}

    async def invalid(_connection: _Connection) -> Mapping[str, Any]:
        return invalid_snapshot

    with pytest.raises(IsolatedDryRunContractError, match="snapshot is invalid"):
        await execute_isolated_dry_run(
            _Connection(),
            plan,
            expected_plan_digest=plan["plan_digest"],
            capture_snapshot=invalid,
        )

    _empty, wrong_target_snapshot = _snapshots()

    async def wrong_base(_connection: _Connection) -> Mapping[str, Any]:
        return wrong_target_snapshot

    with pytest.raises(IsolatedDryRunContractError, match="planned base"):
        await execute_isolated_dry_run(
            _Connection(),
            plan,
            expected_plan_digest=plan["plan_digest"],
            capture_snapshot=wrong_base,
        )


@pytest.mark.asyncio
async def test_masks_version_and_transaction_start_failures() -> None:
    base, target = _models()
    base_snapshot, _target_snapshot = _snapshots()
    plan = compile_migration_plan(base, target)

    async def capture(_connection: _Connection) -> Mapping[str, Any]:
        return base_snapshot

    class VersionFailure(_Connection):
        async def fetchval(self, query: str) -> int:
            raise RuntimeError("secret version failure")

    with pytest.raises(IsolatedDryRunContractError) as captured:
        await execute_isolated_dry_run(
            VersionFailure(),
            plan,
            expected_plan_digest=plan["plan_digest"],
            capture_snapshot=capture,
        )
    assert str(captured.value) == "isolated PostgreSQL version check failed"
    assert captured.value.__cause__ is None

    class StartFailureTransaction(_Transaction):
        async def start(self) -> None:
            raise RuntimeError("secret start failure")

    class StartFailure(_Connection):
        def transaction(self) -> _Transaction:
            return StartFailureTransaction(self)

    start_failure = StartFailure()
    with pytest.raises(IsolatedDryRunContractError, match="statement failed"):
        await execute_isolated_dry_run(
            start_failure,
            plan,
            expected_plan_digest=plan["plan_digest"],
            capture_snapshot=capture,
        )
    assert ("rollback",) not in start_failure.calls


@pytest.mark.asyncio
async def test_preserves_cancellation_during_capture_and_version_check() -> None:
    base, target = _models()
    plan = compile_migration_plan(base, target)

    async def cancelled_capture(_connection: _Connection) -> Mapping[str, Any]:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await execute_isolated_dry_run(
            _Connection(),
            plan,
            expected_plan_digest=plan["plan_digest"],
            capture_snapshot=cancelled_capture,
        )

    class CancelledVersion(_Connection):
        async def fetchval(self, query: str) -> int:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await execute_isolated_dry_run(
            CancelledVersion(),
            plan,
            expected_plan_digest=plan["plan_digest"],
            capture_snapshot=cancelled_capture,
        )


@pytest.mark.asyncio
async def test_masks_rollback_cleanup_failure_without_hiding_primary_failure() -> None:
    base, target = _models()
    base_snapshot, _target_snapshot = _snapshots()
    plan = compile_migration_plan(base, target)

    async def capture(_connection: _Connection) -> Mapping[str, Any]:
        return base_snapshot

    class RollbackFailureTransaction(_Transaction):
        async def rollback(self) -> None:
            raise RuntimeError("secret rollback failure")

    class RollbackFailureConnection(_Connection):
        def transaction(self) -> _Transaction:
            return RollbackFailureTransaction(self)

    connection = RollbackFailureConnection()
    connection.fail_statement = plan["statements"][0]["sql"]
    with pytest.raises(IsolatedDryRunContractError) as captured:
        await execute_isolated_dry_run(
            connection,
            plan,
            expected_plan_digest=plan["plan_digest"],
            capture_snapshot=capture,
        )
    assert str(captured.value) == "isolated dry-run statement failed"
    assert captured.value.__cause__ is None
