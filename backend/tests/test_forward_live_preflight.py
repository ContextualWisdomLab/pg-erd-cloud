from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import pytest

from app.forward.live_preflight import (
    LivePreflightContractError,
    compare_live_preflight_snapshot,
    compile_live_preflight_queries,
    execute_live_preflight,
)
from app.forward.schema_model import schema_model_digest
from app.forward.snapshot_adapter import snapshot_to_schema_model


def _plan(*preconditions: Mapping[str, object]) -> dict[str, object]:
    return {
        "can_dry_run": True,
        "blockers": [],
        "statements": [
            {
                "kind": "alter_column_type",
                "preconditions": [dict(item) for item in preconditions],
            }
        ],
    }


def _snapshot() -> dict[str, Any]:
    return {
        "snapshot_contract_version": 1,
        "server_version_num": 180002,
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
                "is_not_null": True,
                "column_position": 1,
            }
        ],
        "pk_columns": [],
        "constraints": [],
        "fk_edges": [],
        "indexes": [],
    }


def test_compares_strict_snapshot_digest_without_execution_authority() -> None:
    snapshot = _snapshot()
    observed_digest = schema_model_digest(snapshot_to_schema_model(snapshot))
    plan = _plan()
    plan["base_digest"] = observed_digest

    assert compare_live_preflight_snapshot(plan, snapshot) == {
        "observed_base_digest": observed_digest,
        "matches_plan_base": True,
    }

    snapshot["relations"][0]["relation_name"] = "Changed"
    drifted_digest = schema_model_digest(snapshot_to_schema_model(snapshot))
    assert compare_live_preflight_snapshot(plan, snapshot) == {
        "observed_base_digest": drifted_digest,
        "matches_plan_base": False,
    }


@pytest.mark.parametrize("base_digest", [None, True, "A" * 64, "a" * 63])
def test_rejects_invalid_planned_base_digest(base_digest: object) -> None:
    plan = _plan()
    plan["base_digest"] = base_digest

    with pytest.raises(LivePreflightContractError, match="base digest is invalid"):
        compare_live_preflight_snapshot(plan, _snapshot())


def test_snapshot_comparison_fails_closed_for_unsupported_target_semantics() -> None:
    snapshot = _snapshot()
    snapshot["relations"][0]["relation_kind"] = "v"
    plan = _plan()
    plan["base_digest"] = "a" * 64

    with pytest.raises(LivePreflightContractError, match="relation kind"):
        compare_live_preflight_snapshot(plan, snapshot)


def test_compiles_bounded_preconditions_with_postgresql_identifier_quoting() -> None:
    queries = compile_live_preflight_queries(
        _plan(
            {
                "kind": "table_is_empty",
                "schema_name": "Sales Data",
                "table_name": 'Order "Item"',
            },
            {
                "kind": "no_null_values",
                "schema_name": "Sales Data",
                "table_name": 'Order "Item"',
                "column_name": "Item ID",
            },
            {
                "kind": "castable_values",
                "schema_name": "Sales Data",
                "table_name": 'Order "Item"',
                "column_name": "Item ID",
                "target_data_type": "numeric(12,2)",
            },
        )
    )

    assert [query.kind for query in queries] == [
        "table_is_empty",
        "no_null_values",
        "castable_values",
    ]
    assert queries[0].sql == (
        'SELECT NOT EXISTS (SELECT 1 FROM "Sales Data"."Order ""Item""" LIMIT 1)'
    )
    assert queries[1].sql == (
        'SELECT NOT EXISTS (SELECT 1 FROM "Sales Data"."Order ""Item""" '
        'WHERE "Item ID" IS NULL LIMIT 1)'
    )
    assert queries[2].sql == (
        'SELECT COALESCE(bool_and(("Item ID")::numeric(12,2) IS NOT NULL), TRUE) '
        'FROM "Sales Data"."Order ""Item""" WHERE "Item ID" IS NOT NULL'
    )


@pytest.mark.parametrize(
    "precondition, message",
    [
        (
            {
                "kind": "row_count_below",
                "schema_name": "public",
                "table_name": "orders",
            },
            "unsupported live preflight precondition",
        ),
        (
            {
                "kind": "table_is_empty",
                "schema_name": "public",
                "table_name": "orders",
                "unexpected": "field",
            },
            "unrecognized field",
        ),
        (
            {
                "kind": "castable_values",
                "schema_name": "public",
                "table_name": "orders",
                "column_name": "amount",
                "target_data_type": "integer); DROP TABLE orders; --",
            },
            "unsupported data type",
        ),
    ],
)
def test_rejects_unknown_or_tampered_preconditions(
    precondition: Mapping[str, object], message: str
) -> None:
    with pytest.raises(LivePreflightContractError, match=message):
        compile_live_preflight_queries(_plan(precondition))


@pytest.mark.parametrize(
    "schema_name, message",
    [
        (42, "identifier must be text"),
        ("", "identifier is invalid"),
        ("bad\x00name", "identifier is invalid"),
        ("a" * 64, "identifier is too large"),
    ],
)
def test_rejects_invalid_postgresql_identifiers(
    schema_name: object, message: str
) -> None:
    with pytest.raises(LivePreflightContractError, match=message):
        compile_live_preflight_queries(
            _plan(
                {
                    "kind": "table_is_empty",
                    "schema_name": schema_name,
                    "table_name": "orders",
                }
            )
        )


@pytest.mark.parametrize(
    "precondition, message",
    [
        ({"kind": "table_is_empty", "schema_name": "public"}, "missing field"),
        (
            {"kind": 7, "schema_name": "public", "table_name": "orders"},
            "kind is invalid",
        ),
    ],
)
def test_rejects_missing_fields_and_non_text_kinds(
    precondition: Mapping[str, object], message: str
) -> None:
    with pytest.raises(LivePreflightContractError, match=message):
        compile_live_preflight_queries(_plan(precondition))


@pytest.mark.parametrize(
    "plan, message",
    [
        (
            {"can_dry_run": False, "blockers": [], "statements": []},
            "cannot enter",
        ),
        (
            {"can_dry_run": True, "blockers": [{"code": "blocked"}], "statements": []},
            "cannot enter",
        ),
        (
            {"can_dry_run": True, "blockers": [], "statements": "invalid"},
            "statements must be a list",
        ),
        (
            {"can_dry_run": True, "blockers": [], "statements": ["invalid"]},
            "statement must be an object",
        ),
        (
            {
                "can_dry_run": True,
                "blockers": [],
                "statements": [{"preconditions": "invalid"}],
            },
            "preconditions must be a list",
        ),
        (
            {
                "can_dry_run": True,
                "blockers": [],
                "statements": [{"preconditions": ["invalid"]}],
            },
            "precondition must be an object",
        ),
    ],
)
def test_rejects_non_executable_or_malformed_plan_shapes(
    plan: Mapping[str, object], message: str
) -> None:
    with pytest.raises(LivePreflightContractError, match=message):
        compile_live_preflight_queries(plan)


def test_rejects_more_than_the_bounded_query_count() -> None:
    precondition = {
        "kind": "table_is_empty",
        "schema_name": "public",
        "table_name": "orders",
    }
    plan = {
        "can_dry_run": True,
        "blockers": [],
        "statements": [
            {"kind": "add_column", "preconditions": [precondition]}
            for _ in range(1001)
        ],
    }

    with pytest.raises(LivePreflightContractError, match="too many queries"):
        compile_live_preflight_queries(plan)


class _FakeTransaction:
    def __init__(self, connection: "_FakeConnection") -> None:
        self.connection = connection

    async def start(self) -> None:
        self.connection.started = True

    async def commit(self) -> None:
        self.connection.committed = True

    async def rollback(self) -> None:
        self.connection.rolled_back = True


class _FakePreparedStatement:
    def __init__(self, connection: "_FakeConnection", sql: str) -> None:
        self.connection = connection
        self.sql = sql

    async def fetchval(self, *, timeout: float | None = None) -> object:
        return await self.connection.fetch_prepared(self.sql, timeout=timeout)


class _FakeConnection:
    def __init__(self, results: list[object]) -> None:
        self.results = iter(results)
        self.transaction_options: dict[str, object] | None = None
        self.started = False
        self.committed = False
        self.rolled_back = False
        self.executed: list[tuple[str, tuple[object, ...]]] = []
        self.prepared: list[str] = []
        self.queries: list[tuple[str, float | None]] = []

    def transaction(self, **kwargs: object) -> _FakeTransaction:
        self.transaction_options = kwargs
        return _FakeTransaction(self)

    async def execute(self, sql: str, *args: object) -> None:
        self.executed.append((sql, args))

    async def prepare(self, sql: str) -> _FakePreparedStatement:
        self.prepared.append(sql)
        return _FakePreparedStatement(self, sql)

    async def fetch_prepared(
        self, sql: str, *, timeout: float | None = None
    ) -> object:
        self.queries.append((sql, timeout))
        return next(self.results)


class _FailingConnection(_FakeConnection):
    async def fetch_prepared(
        self, sql: str, *, timeout: float | None = None
    ) -> object:
        self.queries.append((sql, timeout))
        raise RuntimeError("postgresql://user:secret@db.example.com/app row=private")


class _CancelledConnection(_FakeConnection):
    async def fetch_prepared(
        self, sql: str, *, timeout: float | None = None
    ) -> object:
        self.queries.append((sql, timeout))
        raise asyncio.CancelledError


@pytest.mark.asyncio
async def test_executes_only_bounded_reads_in_one_read_only_transaction() -> None:
    connection = _FakeConnection([True, False])
    plan = _plan(
        {
            "kind": "table_is_empty",
            "schema_name": "public",
            "table_name": "orders",
        },
        {
            "kind": "no_null_values",
            "schema_name": "public",
            "table_name": "orders",
            "column_name": "customer_id",
        },
    )

    evidence = await execute_live_preflight(
        connection, plan, statement_timeout_ms=2500
    )

    assert connection.transaction_options == {
        "isolation": "repeatable_read",
        "readonly": True,
    }
    assert connection.started is True
    assert connection.committed is True
    assert connection.rolled_back is False
    assert connection.executed == [
        (
            "SELECT pg_catalog.set_config('statement_timeout', $1, true)",
            ("2500ms",),
        )
    ]
    assert connection.prepared == [sql for sql, _ in connection.queries]
    assert [timeout for _, timeout in connection.queries] == [3.5, 3.5]
    assert evidence == {
        "passed": False,
        "checks": [
            {
                "statement_index": 0,
                "precondition_index": 0,
                "kind": "table_is_empty",
                "passed": True,
            },
            {
                "statement_index": 0,
                "precondition_index": 1,
                "kind": "no_null_values",
                "passed": False,
            },
        ],
    }


@pytest.mark.asyncio
async def test_rejects_non_boolean_database_evidence_without_row_values() -> None:
    connection = _FakeConnection(["secret row value"])

    with pytest.raises(
        LivePreflightContractError, match="database result is not boolean"
    ):
        await execute_live_preflight(
            connection,
            _plan(
                {
                    "kind": "table_is_empty",
                    "schema_name": "public",
                    "table_name": "orders",
                }
            ),
        )

    assert connection.rolled_back is True


@pytest.mark.asyncio
async def test_replaces_database_failures_with_a_fixed_non_secret_error() -> None:
    connection = _FailingConnection([])

    with pytest.raises(LivePreflightContractError) as captured:
        await execute_live_preflight(
            connection,
            _plan(
                {
                    "kind": "table_is_empty",
                    "schema_name": "public",
                    "table_name": "orders",
                }
            ),
        )

    assert str(captured.value) == "live preflight query failed"
    assert captured.value.__cause__ is None
    assert connection.rolled_back is True


@pytest.mark.parametrize("timeout", ["5000", True, 0, 60_001])
@pytest.mark.asyncio
async def test_rejects_invalid_statement_timeouts(timeout: object) -> None:
    with pytest.raises(LivePreflightContractError, match="timeout is invalid"):
        await execute_live_preflight(  # type: ignore[arg-type]
            _FakeConnection([]),
            _plan(),
            statement_timeout_ms=timeout,
        )


@pytest.mark.asyncio
async def test_propagates_cancellation_after_rolling_back() -> None:
    connection = _CancelledConnection([])

    with pytest.raises(asyncio.CancelledError):
        await execute_live_preflight(
            connection,
            _plan(
                {
                    "kind": "table_is_empty",
                    "schema_name": "public",
                    "table_name": "orders",
                }
            ),
        )

    assert connection.rolled_back is True
