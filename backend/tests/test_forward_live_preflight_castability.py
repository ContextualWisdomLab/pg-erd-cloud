"""Snapshot-bound castability savepoint regression tests."""

from __future__ import annotations

from typing import Any

import asyncpg
import pytest

from app.forward.live_preflight import (
    LivePreflightContractError,
    execute_bound_live_preflight,
    execute_live_preflight,
)
from app.forward.schema_model import schema_model_digest
from app.forward.snapshot_adapter import snapshot_to_schema_model


def _snapshot() -> dict[str, Any]:
    """Build one strict snapshot for the bound fingerprint evidence."""

    return {
        "snapshot_contract_version": 1,
        "server_version_num": 180002,
        "schemas": [{"schema_oid": 11, "schema_name": "public"}],
        "relations": [
            {
                "relation_oid": 42,
                "schema_name": "public",
                "relation_name": "orders",
                "relation_kind": "r",
            }
        ],
        "columns": [
            {
                "relation_oid": 42,
                "column_name": "good_amount",
                "data_type": "text",
                "is_not_null": False,
                "column_position": 1,
            },
            {
                "relation_oid": 42,
                "column_name": "bad_amount",
                "data_type": "text",
                "is_not_null": False,
                "column_position": 2,
            },
        ],
        "pk_columns": [],
        "constraints": [],
        "fk_edges": [],
        "indexes": [],
    }


def _plan(base_digest: str) -> dict[str, object]:
    """Build two casts and one ordinary read in deterministic order."""

    return {
        "base_digest": base_digest,
        "can_dry_run": True,
        "blockers": [],
        "statements": [
            {
                "preconditions": [
                    {
                        "kind": "castable_values",
                        "schema_name": "public",
                        "table_name": "orders",
                        "column_name": "good_amount",
                        "target_data_type": "integer",
                    },
                    {
                        "kind": "castable_values",
                        "schema_name": "public",
                        "table_name": "orders",
                        "column_name": "bad_amount",
                        "target_data_type": "integer",
                    },
                    {
                        "kind": "table_is_empty",
                        "schema_name": "public",
                        "table_name": "orders",
                    },
                ]
            }
        ],
    }


class _UncastableValue(asyncpg.DataError):
    """Represent one PostgreSQL class-22 cast failure with private detail."""


class _FakeTransaction:
    """Track one outer transaction or nested savepoint lifecycle."""

    def __init__(self, connection: "_FakeConnection", *, nested: bool) -> None:
        self.connection = connection
        self.nested = nested

    async def start(self) -> None:
        if self.nested:
            self.connection.savepoint_started += 1
        else:
            self.connection.outer_started = True

    async def commit(self) -> None:
        if self.nested:
            self.connection.savepoint_committed += 1
        else:
            self.connection.outer_committed = True

    async def rollback(self) -> None:
        if self.nested:
            self.connection.savepoint_rolled_back += 1
        else:
            self.connection.outer_rolled_back = True


class _FakePreparedStatement:
    """Return booleans except for one deliberately uncastable column."""

    def __init__(self, sql: str) -> None:
        self.sql = sql

    async def fetchval(self, *, timeout: float) -> bool:
        assert timeout > 0
        if '"bad_amount"' in self.sql:
            raise _UncastableValue(
                "invalid input syntax contains private target data"
            )
        return True


class _FakeConnection:
    """Expose the asyncpg surface used by the live-preflight primitive."""

    def __init__(self) -> None:
        self.outer_started = False
        self.outer_committed = False
        self.outer_rolled_back = False
        self.savepoint_started = 0
        self.savepoint_committed = 0
        self.savepoint_rolled_back = 0
        self.prepared: list[str] = []

    def transaction(self, **options: object) -> _FakeTransaction:
        return _FakeTransaction(self, nested=not bool(options))

    async def execute(self, sql: str, *args: object) -> None:
        assert "statement_timeout" in sql
        assert len(args) == 1

    async def prepare(self, sql: str) -> _FakePreparedStatement:
        self.prepared.append(sql)
        return _FakePreparedStatement(sql)


@pytest.mark.asyncio
async def test_bound_cast_data_error_becomes_false_without_aborting_snapshot() -> None:
    """Keep class-22 data failure as bounded evidence and continue later checks."""

    snapshot = _snapshot()
    base_digest = schema_model_digest(snapshot_to_schema_model(snapshot))
    connection = _FakeConnection()

    async def capture_snapshot(_: _FakeConnection) -> dict[str, Any]:
        return snapshot

    evidence = await execute_bound_live_preflight(
        connection,  # type: ignore[arg-type]
        _plan(base_digest),
        capture_snapshot=capture_snapshot,  # type: ignore[arg-type]
    )

    assert evidence == {
        "preconditions_passed": False,
        "checks": [
            {
                "statement_index": 0,
                "precondition_index": 0,
                "kind": "castable_values",
                "passed": True,
            },
            {
                "statement_index": 0,
                "precondition_index": 1,
                "kind": "castable_values",
                "passed": False,
            },
            {
                "statement_index": 0,
                "precondition_index": 2,
                "kind": "table_is_empty",
                "passed": True,
            },
        ],
        "observed_base_digest": base_digest,
        "matches_plan_base": True,
    }
    assert connection.outer_started is True
    assert connection.outer_committed is True
    assert connection.outer_rolled_back is False
    assert connection.savepoint_started == 2
    assert connection.savepoint_committed == 1
    assert connection.savepoint_rolled_back == 1
    assert len(connection.prepared) == 3


@pytest.mark.asyncio
async def test_unbound_cast_data_error_remains_a_sanitized_non_success() -> None:
    """Do not promote an unbound cast result into authoritative data evidence."""

    connection = _FakeConnection()

    with pytest.raises(LivePreflightContractError) as captured:
        await execute_live_preflight(
            connection,  # type: ignore[arg-type]
            _plan("a" * 64),
        )

    assert str(captured.value) == "live preflight query failed"
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert connection.outer_committed is False
    assert connection.outer_rolled_back is True
    assert connection.savepoint_started == 0
