"""Execution-neutral pre-apply revalidation manifest contract tests."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping
from typing import Any

import asyncpg
import pytest

from app.forward.migration_plan import COMPILER_VERSION
from app.forward.pre_apply_revalidation import (
    PreApplyRevalidationContractError,
    PreApplyRevalidationManifest,
    assess_pre_apply_revalidation_observation,
    capture_pre_apply_revalidation_observation,
    compile_apply_privilege_queries,
    compile_pre_apply_revalidation_manifest,
)
from app.forward.schema_model import schema_model_digest
from app.forward.snapshot_adapter import snapshot_to_schema_model


def _statement(
    *,
    kind: str = "alter_column_type",
    schema_name: str = "Sales Data",
    table_name: str = 'Order "Item"',
    precondition_schema: str | None = None,
    precondition_table: str | None = None,
    required_privileges: list[str] | None = None,
) -> dict[str, object]:
    """Build one exact compiler-v1 statement with a data precondition."""

    return {
        "kind": kind,
        "target": f"{schema_name}.{table_name}.amount",
        "object_ref": {
            "schema_name": schema_name,
            "table_name": table_name,
            "column_name": "amount",
        },
        "sql": "server-owned and never parsed by this boundary",
        "transactional": True,
        "dependencies": [],
        "dependency_refs": [],
        "reversible": False,
        "risk": {
            "severity": "warning",
            "lock_mode": "ACCESS EXCLUSIVE",
            "possible_rewrite": True,
            "table_scan": True,
            "data_loss": False,
            "detail": "bounded test fixture",
        },
        "required_privileges": (
            required_privileges if required_privileges is not None else ["OWNER"]
        ),
        "preconditions": [
            {
                "kind": "no_null_values",
                "schema_name": precondition_schema or schema_name,
                "table_name": precondition_table or table_name,
                "column_name": "amount",
            }
        ],
    }


def _signed_plan(*statements: dict[str, object]) -> dict[str, object]:
    """Build and sign the exact immutable plan shape used by compiler v1."""

    plan: dict[str, object] = {
        "compiler_version": COMPILER_VERSION,
        "snapshot_contract_version": 1,
        "postgresql_major": 18,
        "base_digest": "a" * 64,
        "target_digest": "b" * 64,
        "statements": list(statements),
        "proposed_statements": [],
        "blockers": [],
        "risk_summary": {"safe": 0, "warning": len(statements), "destructive": 0},
        "requires_destructive_confirmation": False,
        "can_dry_run": True,
    }
    encoded = json.dumps(
        plan,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    plan["plan_digest"] = hashlib.sha256(encoded).hexdigest()
    return plan


def _new_object_statement(
    *, kind: str, schema_name: str, table_name: str | None = None
) -> dict[str, object]:
    """Build one exact compiler-v1 CREATE statement without target access."""

    object_ref = {"schema_name": schema_name}
    lock_mode = "none"
    target = schema_name
    if table_name is not None:
        object_ref["table_name"] = table_name
        lock_mode = "ACCESS EXCLUSIVE"
        target = f"{schema_name}.{table_name}"
    return {
        "kind": kind,
        "target": target,
        "object_ref": object_ref,
        "sql": "server-owned and never parsed by this boundary",
        "transactional": True,
        "dependencies": [],
        "dependency_refs": [],
        "reversible": True,
        "risk": {
            "severity": "safe",
            "lock_mode": lock_mode,
            "possible_rewrite": False,
            "table_scan": False,
            "data_loss": False,
            "detail": "bounded test fixture",
        },
        "required_privileges": ["CREATE"],
        "preconditions": [],
    }


def _resign(plan: dict[str, object]) -> None:
    """Replace the claimed digest after an intentional fixture mutation."""

    plan.pop("plan_digest", None)
    encoded = json.dumps(
        plan,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    plan["plan_digest"] = hashlib.sha256(encoded).hexdigest()


def _observation(
    manifest: PreApplyRevalidationManifest,
    *,
    observed_base_digest: str | None = None,
) -> dict[str, object]:
    """Build complete positional evidence for one compiled manifest."""

    return {
        "plan_digest": manifest.plan_digest,
        "observed_base_digest": observed_base_digest or manifest.base_digest,
        "privileges": [
            {
                "statement_index": requirement.statement_index,
                "privilege": requirement.privilege,
                "scope": requirement.scope,
                "schema_name": requirement.schema_name,
                "table_name": requirement.table_name,
                "allowed": True,
            }
            for requirement in manifest.privilege_requirements
        ],
        "preconditions": [
            {
                "statement_index": query.statement_index,
                "precondition_index": query.precondition_index,
                "kind": query.kind,
                "passed": True,
            }
            for query in manifest.precondition_queries
        ],
    }


def _strict_snapshot() -> dict[str, Any]:
    """Build one strict PostgreSQL snapshot for capture-bound revalidation."""

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
                "column_name": "amount",
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


class _CaptureTransaction:
    """Record the bounded transaction lifecycle used by the capture primitive."""

    def __init__(self, connection: "_CaptureConnection") -> None:
        self.connection = connection
        self.started = False
        self.committed = False
        self.rolled_back = False

    async def start(self) -> None:
        self.started = True
        self.connection.started = True

    async def commit(self) -> None:
        self.committed = True
        self.connection.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True
        self.connection.rolled_back = True


class _CaptureConnection:
    """Minimal asyncpg-shaped connection with ordered boolean observations."""

    def __init__(self, results: list[object]) -> None:
        self.results = iter(results)
        self.transaction_options: dict[str, object] | None = None
        self.started = False
        self.committed = False
        self.rolled_back = False
        self.transactions: list[_CaptureTransaction] = []
        self.executed: list[tuple[str, tuple[object, ...]]] = []
        self.queries: list[tuple[str, tuple[object, ...], float | None]] = []

    def transaction(self, **kwargs: object) -> _CaptureTransaction:
        if kwargs:
            self.transaction_options = kwargs
        transaction = _CaptureTransaction(self)
        self.transactions.append(transaction)
        return transaction

    async def execute(self, sql: str, *args: object) -> None:
        self.executed.append((sql, args))

    async def fetchval(
        self,
        sql: str,
        *args: object,
        timeout: float | None = None,
    ) -> object:
        self.queries.append((sql, args, timeout))
        result = next(self.results)
        if isinstance(result, BaseException):
            raise result
        return result


class _FailingCaptureConnection(_CaptureConnection):
    """Raise one credential-bearing target error for redaction assertions."""

    async def fetchval(
        self,
        sql: str,
        *args: object,
        timeout: float | None = None,
    ) -> object:
        self.queries.append((sql, args, timeout))
        raise RuntimeError("postgresql://user:secret@target/private-row")


@pytest.mark.asyncio
async def test_captures_complete_observation_in_one_read_only_target_snapshot() -> None:
    """Fresh digest, privilege, and precondition facts share one connection."""

    snapshot = _strict_snapshot()
    base_digest = schema_model_digest(snapshot_to_schema_model(snapshot))
    plan = _signed_plan(_statement())
    plan["base_digest"] = base_digest
    _resign(plan)
    connection = _CaptureConnection([True, True])
    captured_connections: list[object] = []

    async def capture_snapshot(candidate: object) -> Mapping[str, object]:
        assert connection.started is True
        captured_connections.append(candidate)
        return snapshot

    assessment = await capture_pre_apply_revalidation_observation(
        connection,
        plan,
        expected_plan_digest=plan["plan_digest"],
        capture_snapshot=capture_snapshot,
        statement_timeout_ms=750,
    )

    assert captured_connections == [connection]
    assert connection.transaction_options == {
        "isolation": "repeatable_read",
        "readonly": True,
    }
    assert connection.executed == [
        (
            "SELECT pg_catalog.set_config('statement_timeout', $1, true)",
            ("750",),
        )
    ]
    assert [args for _sql, args, _timeout in connection.queries] == [
        ("Sales Data", 'Order "Item"'),
        (),
    ]
    assert assessment.observed_base_digest == base_digest
    assert assessment.base_matches is True
    assert assessment.privileges_satisfied is True
    assert assessment.preconditions_satisfied is True
    assert connection.committed is True
    assert connection.rolled_back is False


@pytest.mark.asyncio
async def test_capture_preserves_negative_facts_without_apply_authority() -> None:
    """Drift, privilege denial, and failed checks remain explicit booleans."""

    snapshot = _strict_snapshot()
    plan = _signed_plan(_statement())
    connection = _CaptureConnection([False, False])

    async def capture_snapshot(_candidate: object) -> Mapping[str, object]:
        return snapshot

    assessment = await capture_pre_apply_revalidation_observation(
        connection,
        plan,
        expected_plan_digest=plan["plan_digest"],
        capture_snapshot=capture_snapshot,
    )

    assert assessment.base_matches is False
    assert assessment.privileges_satisfied is False
    assert assessment.preconditions_satisfied is False
    assert connection.committed is True


@pytest.mark.asyncio
async def test_capture_rolls_back_and_sanitizes_target_failure() -> None:
    """Driver and callback detail never escapes the capture boundary."""

    snapshot = _strict_snapshot()
    base_digest = schema_model_digest(snapshot_to_schema_model(snapshot))
    plan = _signed_plan(_statement())
    plan["base_digest"] = base_digest
    _resign(plan)
    connection = _FailingCaptureConnection([])

    async def capture_snapshot(_candidate: object) -> Mapping[str, object]:
        return snapshot

    with pytest.raises(
        PreApplyRevalidationContractError,
        match="^pre-apply revalidation capture failed$",
    ) as failure:
        await capture_pre_apply_revalidation_observation(
            connection,
            plan,
            expected_plan_digest=plan["plan_digest"],
            capture_snapshot=capture_snapshot,
        )

    assert "secret" not in str(failure.value)
    assert "private-row" not in str(failure.value)
    assert connection.rolled_back is True
    assert connection.committed is False


@pytest.mark.asyncio
async def test_capture_records_cast_data_failure_as_negative_evidence() -> None:
    """A cast failure rolls back its savepoint and remains a false fact."""

    snapshot = _strict_snapshot()
    base_digest = schema_model_digest(snapshot_to_schema_model(snapshot))
    plan = _signed_plan(_statement())
    plan["base_digest"] = base_digest
    statements = plan["statements"]
    assert isinstance(statements, list)
    statement = statements[0]
    assert isinstance(statement, dict)
    statement["preconditions"] = [
        {
            "kind": "castable_values",
            "schema_name": "Sales Data",
            "table_name": 'Order "Item"',
            "column_name": "amount",
            "target_data_type": "integer",
        }
    ]
    _resign(plan)
    connection = _CaptureConnection(
        [True, asyncpg.DataError("invalid input value")]
    )

    async def capture_snapshot(_candidate: object) -> Mapping[str, object]:
        return snapshot

    assessment = await capture_pre_apply_revalidation_observation(
        connection,
        plan,
        expected_plan_digest=plan["plan_digest"],
        capture_snapshot=capture_snapshot,
    )

    assert assessment.base_matches is True
    assert assessment.privileges_satisfied is True
    assert assessment.preconditions_satisfied is False
    outer_transaction, savepoint = connection.transactions
    assert outer_transaction.committed is True
    assert outer_transaction.rolled_back is False
    assert savepoint.committed is False
    assert savepoint.rolled_back is True


@pytest.mark.asyncio
async def test_capture_preserves_cancellation_after_best_effort_rollback() -> None:
    """Cancellation is not converted into a contract or target failure."""

    plan = _signed_plan(_statement())
    connection = _CaptureConnection([])

    async def capture_snapshot(_candidate: object) -> Mapping[str, object]:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await capture_pre_apply_revalidation_observation(
            connection,
            plan,
            expected_plan_digest=plan["plan_digest"],
            capture_snapshot=capture_snapshot,
        )

    assert len(connection.transactions) == 1
    assert connection.transactions[0].rolled_back is True
    assert connection.transactions[0].committed is False


@pytest.mark.asyncio
@pytest.mark.parametrize("statement_timeout_ms", [True, 0, 60_001, "5000"])
async def test_capture_rejects_invalid_timeout_before_target_access(
    statement_timeout_ms: object,
) -> None:
    """Malformed timeout input cannot open a target transaction."""

    plan = _signed_plan(_statement())
    connection = _CaptureConnection([])

    async def capture_snapshot(_candidate: object) -> Mapping[str, object]:
        return _strict_snapshot()

    with pytest.raises(
        PreApplyRevalidationContractError,
        match="statement timeout is invalid",
    ):
        await capture_pre_apply_revalidation_observation(
            connection,
            plan,
            expected_plan_digest=plan["plan_digest"],
            capture_snapshot=capture_snapshot,
            statement_timeout_ms=statement_timeout_ms,  # type: ignore[arg-type]
        )

    assert connection.transaction_options is None


def test_binds_signed_plan_locks_and_checks_without_target_access() -> None:
    """Manifest preserves exact authority inputs and deterministic ordering."""

    plan = _signed_plan(_statement())

    manifest = compile_pre_apply_revalidation_manifest(
        plan, expected_plan_digest=plan["plan_digest"]
    )

    assert manifest.plan_digest == plan["plan_digest"]
    assert manifest.compiler_version == COMPILER_VERSION
    assert manifest.snapshot_contract_version == 1
    assert manifest.postgresql_major == 18
    assert manifest.base_digest == "a" * 64
    assert manifest.target_digest == "b" * 64
    assert len(manifest.transaction_segments) == 1
    assert manifest.transaction_segments[0].segment_index == 0
    assert manifest.transaction_segments[0].statement_indexes == (0,)
    assert manifest.transaction_segments[0].transactional is True
    assert [
        (
            requirement.statement_index,
            requirement.privilege,
            requirement.scope,
            requirement.schema_name,
            requirement.table_name,
        )
        for requirement in manifest.privilege_requirements
    ] == [(0, "OWNER", "table", "Sales Data", 'Order "Item"')]
    assert [target.sql for target in manifest.lock_targets] == [
        'LOCK TABLE "Sales Data"."Order ""Item""" IN ACCESS EXCLUSIVE MODE'
    ]
    assert [query.sql for query in manifest.precondition_queries] == [
        'SELECT NOT EXISTS (SELECT 1 FROM "Sales Data"."Order ""Item""" '
        'WHERE "amount" IS NULL LIMIT 1)'
    ]


def test_assesses_complete_bound_observation_without_granting_apply_authority() -> None:
    """Pure assessment derives only evidence booleans from exact manifest rows."""

    plan = _signed_plan(_statement())
    manifest = compile_pre_apply_revalidation_manifest(
        plan, expected_plan_digest=plan["plan_digest"]
    )

    assessment = assess_pre_apply_revalidation_observation(
        manifest,
        _observation(manifest),
    )

    assert assessment.observed_base_digest == "a" * 64
    assert assessment.base_matches is True
    assert assessment.privileges_satisfied is True
    assert assessment.preconditions_satisfied is True


def test_assessment_preserves_negative_observations_as_non_authorizing_facts() -> None:
    """Drift, privilege denial, and failed checks remain explicit evidence."""

    plan = _signed_plan(_statement())
    manifest = compile_pre_apply_revalidation_manifest(
        plan, expected_plan_digest=plan["plan_digest"]
    )
    observation = _observation(manifest, observed_base_digest="c" * 64)
    privileges = observation["privileges"]
    preconditions = observation["preconditions"]
    assert isinstance(privileges, list) and isinstance(preconditions, list)
    privileges[0]["allowed"] = False
    preconditions[0]["passed"] = False

    assessment = assess_pre_apply_revalidation_observation(manifest, observation)

    assert assessment.base_matches is False
    assert assessment.privileges_satisfied is False
    assert assessment.preconditions_satisfied is False


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("unknown_field", "observation contract is invalid"),
        ("wrong_plan", "plan digest does not match"),
        ("missing_privilege", "privilege observations are incomplete"),
        ("wrong_privilege_target", "privilege observation does not match"),
        ("non_boolean_privilege", "privilege result is invalid"),
        ("missing_precondition", "precondition observations are incomplete"),
        ("wrong_precondition_kind", "precondition observation does not match"),
        ("non_boolean_precondition", "precondition result is invalid"),
    ],
)
def test_assessment_rejects_incomplete_or_unbound_observations(
    mutation: str, message: str
) -> None:
    """Untrusted caller evidence must match every manifest position exactly."""

    plan = _signed_plan(_statement())
    manifest = compile_pre_apply_revalidation_manifest(
        plan, expected_plan_digest=plan["plan_digest"]
    )
    observation = _observation(manifest)
    privileges = observation["privileges"]
    preconditions = observation["preconditions"]
    assert isinstance(privileges, list) and isinstance(preconditions, list)

    if mutation == "unknown_field":
        observation["connection_id"] = "not-authority"
    elif mutation == "wrong_plan":
        observation["plan_digest"] = "d" * 64
    elif mutation == "missing_privilege":
        privileges.clear()
    elif mutation == "wrong_privilege_target":
        privileges[0]["table_name"] = "other"
    elif mutation == "non_boolean_privilege":
        privileges[0]["allowed"] = 1
    elif mutation == "missing_precondition":
        preconditions.clear()
    elif mutation == "wrong_precondition_kind":
        preconditions[0]["kind"] = "table_is_empty"
    else:
        preconditions[0]["passed"] = "yes"

    with pytest.raises(PreApplyRevalidationContractError, match=message):
        assess_pre_apply_revalidation_observation(manifest, observation)


def test_compiles_one_ordered_segment_for_multiple_statements() -> None:
    """Compiler-v1 never splits admitted apply work into implicit segments."""

    plan = _signed_plan(
        _statement(schema_name="alpha", table_name="first"),
        _statement(schema_name="zeta", table_name="second"),
    )

    manifest = compile_pre_apply_revalidation_manifest(
        plan, expected_plan_digest=plan["plan_digest"]
    )

    assert len(manifest.transaction_segments) == 1
    assert manifest.transaction_segments[0].statement_indexes == (0, 1)


def test_maps_create_privileges_to_database_and_schema_scopes() -> None:
    """CREATE labels retain their distinct PostgreSQL authority scopes."""

    plan = _signed_plan(
        _new_object_statement(kind="create_schema", schema_name="분석 영역"),
        _new_object_statement(
            kind="create_table",
            schema_name="분석 영역",
            table_name='Event "Log"',
        ),
    )

    manifest = compile_pre_apply_revalidation_manifest(
        plan, expected_plan_digest=plan["plan_digest"]
    )

    assert [
        (
            requirement.statement_index,
            requirement.privilege,
            requirement.scope,
            requirement.schema_name,
            requirement.table_name,
        )
        for requirement in manifest.privilege_requirements
    ] == [
        (0, "CREATE", "database", None, None),
        (1, "CREATE", "schema", "분석 영역", None),
    ]


def test_compiles_parameterized_privilege_probes_without_target_access() -> None:
    """Privilege scopes become bounded catalog reads with data parameters."""

    plan = _signed_plan(
        _new_object_statement(kind="create_schema", schema_name="분석 영역"),
        _new_object_statement(
            kind="create_table",
            schema_name="분석 영역",
            table_name='Event "Log"',
        ),
        _statement(schema_name="분석 영역", table_name='Event "Log"'),
    )
    queries = compile_apply_privilege_queries(
        plan, expected_plan_digest=plan["plan_digest"]
    )

    assert [
        (query.statement_index, query.privilege, query.scope, query.parameters)
        for query in queries
    ] == [
        (0, "CREATE", "database", ()),
        (1, "CREATE", "schema", ("분석 영역",)),
        (2, "OWNER", "table", ("분석 영역", 'Event "Log"')),
    ]
    assert queries[0].sql == (
        "SELECT pg_catalog.has_database_privilege("
        "pg_catalog.current_database(), 'CREATE')"
    )
    assert queries[1].sql == (
        "SELECT pg_catalog.has_schema_privilege($1::text, 'CREATE')"
    )
    assert "pg_catalog.pg_has_role(c.relowner, 'USAGE')" in queries[2].sql
    assert "$1::text" in queries[2].sql and "$2::text" in queries[2].sql


def test_privilege_probe_compiler_rejects_redirected_signed_plan_target() -> None:
    """A stale signature cannot redirect a valid probe to another object."""

    plan = _signed_plan(_statement(schema_name="public", table_name="orders"))
    expected_plan_digest = plan["plan_digest"]
    statements = plan["statements"]
    assert isinstance(statements, list)
    statement = statements[0]
    assert isinstance(statement, dict)
    object_ref = statement["object_ref"]
    assert isinstance(object_ref, dict)
    object_ref["schema_name"] = "other_schema"
    object_ref["table_name"] = "other_table"

    with pytest.raises(
        PreApplyRevalidationContractError, match="plan digest is invalid"
    ):
        compile_apply_privilege_queries(
            plan, expected_plan_digest=expected_plan_digest
        )


def test_compiles_no_transaction_segment_for_a_noop_plan() -> None:
    """A converged no-op plan contains no synthetic executable segment."""

    plan = _signed_plan()

    manifest = compile_pre_apply_revalidation_manifest(
        plan, expected_plan_digest=plan["plan_digest"]
    )

    assert manifest.transaction_segments == ()
    assert manifest.privilege_requirements == ()
    assert manifest.lock_targets == ()
    assert manifest.precondition_queries == ()


def test_rejects_required_privileges_outside_compiler_v1_semantics() -> None:
    """Signed metadata cannot make a weaker or unknown privilege executable."""

    plan = _signed_plan(_statement(required_privileges=["ALTER"]))

    with pytest.raises(
        PreApplyRevalidationContractError, match="required privileges are invalid"
    ):
        compile_pre_apply_revalidation_manifest(
            plan, expected_plan_digest=plan["plan_digest"]
        )


def test_rejects_content_that_no_longer_matches_the_stored_digest() -> None:
    """A caller cannot bind lock/check work from mutated plan content."""

    plan = _signed_plan(_statement())
    expected_digest = plan["plan_digest"]
    plan["postgresql_major"] = 17

    with pytest.raises(
        PreApplyRevalidationContractError, match="plan digest is invalid"
    ):
        compile_pre_apply_revalidation_manifest(
            plan, expected_plan_digest=expected_digest
        )


def test_rejects_noncanonical_plan_content_with_a_fixed_error() -> None:
    """Digest verification never exposes serialization implementation detail."""

    plan = _signed_plan(_statement())
    plan["risk_summary"] = {"warning": {1}}

    with pytest.raises(
        PreApplyRevalidationContractError, match="plan digest is invalid"
    ):
        compile_pre_apply_revalidation_manifest(
            plan, expected_plan_digest="a" * 64
        )


@pytest.mark.parametrize("expected_digest", [None, True, "A" * 64, "a" * 63])
def test_rejects_invalid_expected_plan_digest(expected_digest: object) -> None:
    """Stored digest input must be a canonical lowercase SHA-256 value."""

    plan = _signed_plan(_statement())

    with pytest.raises(
        PreApplyRevalidationContractError, match="expected plan digest is invalid"
    ):
        compile_pre_apply_revalidation_manifest(
            plan, expected_plan_digest=expected_digest
        )


def test_rejects_unknown_plan_fields_even_when_the_content_is_signed() -> None:
    """A future contract cannot silently enter a compiler-v1 apply boundary."""

    plan = _signed_plan(_statement())
    plan["future_authority"] = True
    _resign(plan)

    with pytest.raises(
        PreApplyRevalidationContractError, match="plan contract is invalid"
    ):
        compile_pre_apply_revalidation_manifest(
            plan, expected_plan_digest=plan["plan_digest"]
        )


def test_rejects_precondition_bound_to_a_different_table() -> None:
    """Every data check must describe the statement's structured table ref."""

    plan = _signed_plan(
        _statement(precondition_schema="other", precondition_table="orders")
    )

    with pytest.raises(
        PreApplyRevalidationContractError,
        match="precondition target does not match statement",
    ):
        compile_pre_apply_revalidation_manifest(
            plan, expected_plan_digest=plan["plan_digest"]
        )


def test_rejects_preconditions_without_an_existing_table_lock() -> None:
    """A data check cannot be scheduled unless its relation will be locked."""

    plan = _signed_plan(_statement(kind="create_table"))

    with pytest.raises(
        PreApplyRevalidationContractError, match="precondition target is not locked"
    ):
        compile_pre_apply_revalidation_manifest(
            plan, expected_plan_digest=plan["plan_digest"]
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("compiler_version", "future", "compiler is unsupported"),
        (
            "snapshot_contract_version",
            2,
            "snapshot contract is unsupported",
        ),
        ("proposed_statements", [{}], "proposals are not executable"),
    ],
)
def test_rejects_incompatible_or_review_only_plan_contracts(
    field: str, value: object, message: str
) -> None:
    """Only exact executable compiler-v1 plans can produce a manifest."""

    plan = _signed_plan(_statement())
    plan[field] = value
    _resign(plan)

    with pytest.raises(PreApplyRevalidationContractError, match=message):
        compile_pre_apply_revalidation_manifest(
            plan, expected_plan_digest=plan["plan_digest"]
        )


@pytest.mark.parametrize("postgresql_major", [True, 13, 19, "18"])
def test_rejects_unsupported_postgresql_major(postgresql_major: object) -> None:
    """Manifest compatibility remains bounded to supported PostgreSQL majors."""

    plan = _signed_plan(_statement())
    plan["postgresql_major"] = postgresql_major
    _resign(plan)

    with pytest.raises(
        PreApplyRevalidationContractError, match="PostgreSQL major is invalid"
    ):
        compile_pre_apply_revalidation_manifest(
            plan, expected_plan_digest=plan["plan_digest"]
        )
