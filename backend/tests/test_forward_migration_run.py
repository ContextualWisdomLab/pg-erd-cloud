from __future__ import annotations

import copy
import uuid
from datetime import datetime, timedelta, timezone
from math import nan
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, Mock, patch

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql

from app.forward.migration_plan import compile_migration_plan
from app.forward.migration_run import (
    _expected_live_preflight_checks,
    MigrationDispatchClaim,
    MigrationRunAttemptClaim,
    MigrationRunContractError,
    acquire_migration_run_attempt,
    canonicalize_run_evidence,
    claim_one_migration_dispatch,
    complete_isolated_dry_run,
    complete_live_preflight,
    create_migration_run,
    digest_run_event,
    digest_run_request,
    hash_idempotency_key,
    mark_migration_dispatch_published,
    finish_migration_run_attempt,
    request_migration_run_cancellation,
    renew_migration_run_attempt,
    transition_migration_run,
    validate_run_transition,
)
from app.models import (
    DbConnection,
    MigrationPlan,
    MigrationRun,
    MigrationRunAttempt,
    MigrationRunDispatch,
    MigrationRunEvent,
    SchemaModel,
    SchemaModelRevision,
)


def _queued_migration_run(*, now: datetime) -> MigrationRun:
    """Return one active dry-run row suitable for worker-attempt tests."""

    return MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        migration_plan_uuid=uuid.uuid4(),
        run_kind="dry_run",
        state="queued",
        state_version=1,
        idempotency_key_hash="a" * 64,
        plan_digest="b" * 64,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=uuid.uuid4(),
        cancellation_requested=False,
        evidence_json={},
        created_at=now,
        updated_at=now,
    )


def _migration_plan(
    *, expires_at: datetime | None = None, blocked: bool = False
) -> MigrationPlan:
    now = datetime(2026, 8, 10, tzinfo=timezone.utc)
    plan_json = compile_migration_plan(
        {"format_version": 1, "postgresql_major": 18, "schemas": []},
        {
            "format_version": 1,
            "postgresql_major": 17 if blocked else 18,
            "schemas": [],
        },
    )
    return MigrationPlan(
        migration_plan_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        schema_model_revision_uuid=uuid.uuid4(),
        db_connection_uuid=uuid.uuid4(),
        base_schema_snapshot_uuid=uuid.uuid4(),
        compiler_version=plan_json["compiler_version"],
        base_digest=plan_json["base_digest"],
        target_digest=plan_json["target_digest"],
        statement_digest=plan_json["plan_digest"],
        plan_json=plan_json,
        created_by_user_uuid=uuid.uuid4(),
        expires_at=expires_at or datetime(2026, 8, 11, tzinfo=timezone.utc),
        created_at=now,
    )


def _migration_plan_with_preconditions() -> MigrationPlan:
    """Return one valid plan with a required table-emptiness precondition."""

    base_model = {
        "format_version": 1,
        "postgresql_major": 18,
        "schemas": [
            {
                "schema_name": "public",
                "tables": [
                    {
                        "table_name": "accounts",
                        "comment": None,
                        "columns": [
                            {
                                "column_name": "id",
                                "data_type": "bigint",
                                "nullable": False,
                                "ordinal_position": 1,
                            }
                        ],
                        "primary_key": None,
                        "unique_constraints": [],
                        "foreign_keys": [],
                        "indexes": [],
                        "unsupported_features": [],
                    }
                ],
            }
        ],
    }
    target_model = copy.deepcopy(base_model)
    target_model["schemas"][0]["tables"][0]["columns"].append(
        {
            "column_name": "tenant_id",
            "data_type": "bigint",
            "nullable": False,
            "ordinal_position": 2,
        }
    )
    plan_json = compile_migration_plan(base_model, target_model)
    return MigrationPlan(
        migration_plan_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        schema_model_revision_uuid=uuid.uuid4(),
        db_connection_uuid=uuid.uuid4(),
        base_schema_snapshot_uuid=uuid.uuid4(),
        compiler_version=plan_json["compiler_version"],
        base_digest=plan_json["base_digest"],
        target_digest=plan_json["target_digest"],
        statement_digest=plan_json["plan_digest"],
        plan_json=plan_json,
        created_by_user_uuid=uuid.uuid4(),
        expires_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
        created_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
    )


def _current_revision(
    plan: MigrationPlan, *, actor_uuid: uuid.UUID
) -> tuple[SchemaModelRevision, SchemaModel]:
    """Return one current model/revision binding for apply-intent tests."""

    model = SchemaModel(
        schema_model_uuid=uuid.uuid4(),
        project_space_uuid=plan.project_space_uuid,
        model_name="reviewed model",
        current_revision_number=3,
        created_by_user_uuid=actor_uuid,
    )
    revision = SchemaModelRevision(
        schema_model_revision_uuid=plan.schema_model_revision_uuid,
        schema_model_uuid=model.schema_model_uuid,
        revision_number=model.current_revision_number,
        revision_digest=plan.target_digest,
        model_json={},
        created_by_user_uuid=actor_uuid,
    )
    return revision, model


def test_run_state_machine_separates_dry_run_and_apply_authority() -> None:
    """Dry-run and apply states never cross their separate authority graphs."""

    validate_run_transition("dry_run", "queued", "sandbox_running")
    validate_run_transition("dry_run", "live_preflight_running", "passed")
    validate_run_transition("apply", "queued", "applying")
    validate_run_transition("apply", "reconciling", "outcome_unknown")

    with pytest.raises(MigrationRunContractError, match="invalid transition"):
        validate_run_transition("dry_run", "queued", "applying")
    with pytest.raises(MigrationRunContractError, match="invalid transition"):
        validate_run_transition("apply", "applying", "queued")
    with pytest.raises(MigrationRunContractError, match="unknown run kind"):
        validate_run_transition("preview", "queued", "passed")


def test_idempotency_key_is_bounded_and_stored_only_as_a_digest() -> None:
    """Opaque retry keys are bounded before only their SHA-256 digest persists."""

    assert hash_idempotency_key("retry-한글-1") == hash_idempotency_key(
        "retry-한글-1"
    )
    assert len(hash_idempotency_key("retry-한글-1")) == 64

    for value in ("", "contains\nnewline", "x" * 256):
        with pytest.raises(MigrationRunContractError):
            hash_idempotency_key(value)


def test_run_request_digest_binds_exact_actor_plan_and_intent() -> None:
    """The request digest changes with every execution-authority binding."""

    project_uuid = uuid.uuid4()
    plan_uuid = uuid.uuid4()
    actor_uuid = uuid.uuid4()
    kwargs = {
        "project_space_uuid": project_uuid,
        "migration_plan_uuid": plan_uuid,
        "run_kind": "dry_run",
        "plan_digest": "a" * 64,
        "requested_by_user_uuid": actor_uuid,
    }

    first = digest_run_request(**kwargs)
    assert first == digest_run_request(**kwargs)
    assert len(first) == 64

    for field, value in (
        ("project_space_uuid", uuid.uuid4()),
        ("migration_plan_uuid", uuid.uuid4()),
        ("plan_digest", "b" * 64),
        ("requested_by_user_uuid", uuid.uuid4()),
    ):
        changed = dict(kwargs)
        changed[field] = value
        assert digest_run_request(**changed) != first

    passed_dry_run_uuid = uuid.uuid4()
    apply_digest = digest_run_request(
        **{**kwargs, "run_kind": "apply"},
        passed_dry_run_uuid=passed_dry_run_uuid,
        confirmation_digest="b" * 64,
    )
    assert apply_digest != first
    assert digest_run_request(
        **{**kwargs, "run_kind": "apply"},
        passed_dry_run_uuid=uuid.uuid4(),
        confirmation_digest="b" * 64,
    ) != apply_digest
    assert digest_run_request(
        **{**kwargs, "run_kind": "apply"},
        passed_dry_run_uuid=passed_dry_run_uuid,
        confirmation_digest="c" * 64,
    ) != apply_digest
    with pytest.raises(MigrationRunContractError, match="passed dry run"):
        digest_run_request(
            **{**kwargs, "run_kind": "apply"},
            confirmation_digest="b" * 64,
        )
    with pytest.raises(MigrationRunContractError, match="apply confirmation"):
        digest_run_request(
            **{**kwargs, "run_kind": "apply"},
            passed_dry_run_uuid=passed_dry_run_uuid,
            confirmation_digest="not-a-digest",
        )

    with pytest.raises(MigrationRunContractError, match="run kind"):
        digest_run_request(**{**kwargs, "run_kind": "preview"})
    with pytest.raises(MigrationRunContractError, match="plan digest"):
        digest_run_request(**{**kwargs, "plan_digest": "not-a-digest"})


def test_run_event_digest_binds_order_state_evidence_actor_and_time() -> None:
    """Every durable event field and predecessor participates in its digest."""

    run_uuid = uuid.uuid4()
    actor_uuid = uuid.uuid4()
    created_at = datetime(2026, 8, 10, 2, 3, 4, 5, tzinfo=timezone.utc)
    kwargs = {
        "migration_run_uuid": run_uuid,
        "sequence_number": 2,
        "event_type": "sandbox_started",
        "state_before": "queued",
        "state_after": "sandbox_running",
        "evidence": {"attempt": 1, "sandbox_version": "postgresql-18"},
        "actor_user_uuid": actor_uuid,
        "created_at": created_at,
        "previous_event_digest": "a" * 64,
    }

    first = digest_run_event(**kwargs)
    assert first == digest_run_event(**kwargs)
    assert len(first) == 64

    for field, value in (
        ("sequence_number", 3),
        ("event_type", "sandbox_retried"),
        ("state_before", "sandbox_running"),
        ("state_after", "failed"),
        ("evidence", {"attempt": 2}),
        ("actor_user_uuid", uuid.uuid4()),
        ("created_at", created_at.replace(microsecond=6)),
        ("previous_event_digest", "b" * 64),
    ):
        changed = dict(kwargs)
        changed[field] = value
        assert digest_run_event(**changed) != first

    genesis = {**kwargs, "sequence_number": 1, "previous_event_digest": None}
    assert len(digest_run_event(**genesis)) == 64
    for invalid in (
        {**kwargs, "sequence_number": 1},
        {**kwargs, "previous_event_digest": None},
        {**kwargs, "previous_event_digest": "not-a-digest"},
        {**kwargs, "created_at": created_at.replace(tzinfo=None)},
        {**kwargs, "migration_run_uuid": "not-a-uuid"},
        {**kwargs, "sequence_number": True},
        {**kwargs, "sequence_number": "2"},
        {**kwargs, "sequence_number": 0},
        {**kwargs, "event_type": "invalid event"},
        {**kwargs, "state_after": ""},
        {**kwargs, "state_after": 1},
        {**kwargs, "state_before": ""},
        {**kwargs, "state_before": 1},
        {**kwargs, "actor_user_uuid": "not-a-uuid"},
    ):
        with pytest.raises(MigrationRunContractError):
            digest_run_event(**invalid)


def test_run_evidence_rejects_secret_and_sql_bearing_fields_recursively() -> None:
    """Durable evidence rejects nested SQL, secrets, and connection strings."""

    evidence = canonicalize_run_evidence(
        {
            "statement_count": 2,
            "duration_ms": 25,
            "findings": [{"code": "lock_warning", "object_count": 1}],
        }
    )
    assert evidence["statement_count"] == 2

    for payload in (
        {"dsn": "postgresql://secret"},
        {"nested": {"raw_sql": "DROP TABLE customer_record"}},
        {"events": [{"access_token": "secret"}]},
        {"nested": {"rawSql": "DROP TABLE customer_record"}},
        {"databaseDsn": "postgresql://secret"},
        {"events": [{"accessToken": "secret"}]},
    ):
        with pytest.raises(MigrationRunContractError, match="forbidden evidence field"):
            canonicalize_run_evidence(payload)

    for payload in (
        {"detail": "postgresql://worker:password@db.example/app"},
        {"events": [{"endpoint": "POSTGRES://worker@db.example/app"}]},
    ):
        with pytest.raises(MigrationRunContractError, match="connection string"):
            canonicalize_run_evidence(payload)

    with pytest.raises(MigrationRunContractError, match="too large"):
        canonicalize_run_evidence({"detail": "x" * 16_385})


def test_run_evidence_enforces_every_json_shape_and_resource_bound() -> None:
    """Evidence accepts finite JSON and rejects hostile shapes before storage."""

    assert canonicalize_run_evidence(
        {"finite": 1.25, "empty": None, "flags": [True, 1, "ok"]}
    ) == {"empty": None, "finite": 1.25, "flags": [True, 1, "ok"]}

    nested: dict[str, object] = {}
    cursor = nested
    for _ in range(10):
        child: dict[str, object] = {}
        cursor["child"] = child
        cursor = child

    invalid_cases = (
        ({"value": nan}, "finite"),
        ({str(index): index for index in range(257)}, "too many fields"),
        ({"items": list(range(257))}, "too many items"),
        ({"opaque": b"bytes"}, "unsupported"),
        (nested, "too deep"),
        ({str(index): "x" * 100 for index in range(200)}, "too large"),
    )
    for payload, message in invalid_cases:
        with pytest.raises(MigrationRunContractError, match=message):
            canonicalize_run_evidence(payload)

    with pytest.raises(MigrationRunContractError, match="field name must be text"):
        canonicalize_run_evidence({1: "value"})  # type: ignore[dict-item]


def test_migration_run_persistence_enforces_idempotent_identity_and_state() -> None:
    """ORM constraints preserve run identity, state, and evidence boundaries."""

    assert MigrationRun.__tablename__ == "migration_run"
    assert MigrationRunDispatch.__tablename__ == "migration_run_dispatch"
    assert MigrationRunEvent.__tablename__ == "migration_run_event"

    unique_run_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in MigrationRun.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert (
        "project_space_uuid",
        "run_kind",
        "idempotency_key_hash",
    ) in unique_run_columns
    assert {
        constraint.name
        for constraint in MigrationRun.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_migration_run__run_kind",
        "ck_migration_run__state",
        "ck_migration_run__kind_state",
        "ck_migration_run__state_version",
        "ck_migration_run__latest_event_digest",
        "ck_migration_run__idempotency_key_hash",
        "ck_migration_run__plan_digest",
        "ck_migration_run__request_digest",
        "ck_migration_run__observed_base_digest",
        "ck_migration_run__confirmation_digest",
        "ck_migration_run__apply_confirmation",
    }

    unique_event_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in MigrationRunEvent.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("migration_run_uuid", "sequence_number") in unique_event_columns
    assert {
        constraint.name
        for constraint in MigrationRunEvent.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_migration_run_event__sequence_number",
        "ck_migration_run_event__previous_digest",
        "ck_migration_run_event__previous_digest_format",
        "ck_migration_run_event__event_digest",
        "ck_migration_run_event__event_type",
        "ck_migration_run_event__state_before",
        "ck_migration_run_event__state_after",
    }
    assert "latest_event_digest" in MigrationRun.__table__.columns
    assert "previous_event_digest" in MigrationRunEvent.__table__.columns
    assert "event_digest" in MigrationRunEvent.__table__.columns
    assert {index.name for index in MigrationRun.__table__.indexes} == {
        "ix_migration_run__migration_plan_uuid",
        "ix_migration_run__passed_dry_run_uuid",
        "ix_migration_run__project_state",
    }
    assert {index.name for index in MigrationRunEvent.__table__.indexes} == set()

    run = MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        migration_plan_uuid=uuid.uuid4(),
        run_kind="dry_run",
        state="queued",
        state_version=1,
        idempotency_key_hash="a" * 64,
        plan_digest="b" * 64,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=uuid.uuid4(),
        cancellation_requested=False,
        evidence_json={},
    )
    assert run.state == "queued"
    assert "dsn" not in MigrationRun.__table__.columns
    assert "sql" not in MigrationRunEvent.__table__.columns
    assert {
        column.name for column in MigrationRunDispatch.__table__.columns
    } == {
        "migration_run_dispatch_uuid",
        "migration_run_uuid",
        "dispatch_kind",
        "status",
        "attempt_count",
        "not_before",
        "created_at",
        "published_at",
    }
    assert {
        constraint.name
        for constraint in MigrationRunDispatch.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_migration_run_dispatch__dispatch_kind",
        "ck_migration_run_dispatch__status",
        "ck_migration_run_dispatch__attempt_count",
        "ck_migration_run_dispatch__published_at",
    }
    assert {
        tuple(column.name for column in constraint.columns)
        for constraint in MigrationRunDispatch.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    } == {("migration_run_uuid",)}
    assert {index.name for index in MigrationRunDispatch.__table__.indexes} == {
        "ix_migration_run_dispatch__status_not_before",
    }


def test_migration_run_attempt_persistence_is_lease_bound_and_secret_free() -> None:
    """Attempt history stores only hashes and permits one active owner per run."""

    assert MigrationRunAttempt.__tablename__ == "migration_run_attempt"
    assert {
        column.name for column in MigrationRunAttempt.__table__.columns
    } == {
        "migration_run_attempt_uuid",
        "migration_run_uuid",
        "attempt_number",
        "acquired_state_version",
        "status",
        "worker_identity_hash",
        "signal_lease_token_hash",
        "lease_expires_at",
        "acquired_at",
        "last_heartbeat_at",
        "finished_at",
    }
    assert {
        constraint.name
        for constraint in MigrationRunAttempt.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_migration_run_attempt__attempt_number",
        "ck_migration_run_attempt__acquired_state_version",
        "ck_migration_run_attempt__status",
        "ck_migration_run_attempt__worker_identity_hash",
        "ck_migration_run_attempt__signal_lease_token_hash",
        "ck_migration_run_attempt__timestamps",
    }
    assert {
        tuple(column.name for column in constraint.columns)
        for constraint in MigrationRunAttempt.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    } == {("migration_run_uuid", "attempt_number")}
    assert {index.name for index in MigrationRunAttempt.__table__.indexes} == {
        "ix_migration_run_attempt__active_run",
        "ix_migration_run_attempt__lease_expiry",
    }
    assert {
        column.name for column in MigrationRunAttempt.__table__.columns
    }.isdisjoint(
        {"worker_identity", "signal_lease_token", "dsn", "sql", "plan_json"}
    )


@pytest.mark.asyncio
async def test_attempt_acquire_locks_run_and_creates_first_hashed_claim() -> None:
    """Acquisition serializes on the run and persists hashes, never raw identity."""

    now = datetime(2026, 8, 12, 2, tzinfo=timezone.utc)
    run = _queued_migration_run(now=now)
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[run, None, None]),
        add=Mock(),
    )
    token = uuid.uuid4()

    claim = await acquire_migration_run_attempt(
        session,
        migration_run_uuid=run.migration_run_uuid,
        worker_identity="worker-a",
        signal_lease_token=token,
        lease_seconds=60,
        now=now,
    )

    assert claim.migration_run_uuid == run.migration_run_uuid
    assert claim.attempt_number == 1
    assert claim.acquired_state_version == 1
    assert claim.lease_expires_at == now + timedelta(seconds=60)
    assert session.scalar.await_count == 3
    run_statement = session.scalar.await_args_list[0].args[0]
    assert "FOR UPDATE" in str(
        run_statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    attempt = session.add.call_args.args[0]
    assert isinstance(attempt, MigrationRunAttempt)
    assert attempt.worker_identity_hash != "worker-a"
    assert attempt.signal_lease_token_hash != str(token)
    assert len(attempt.worker_identity_hash) == 64
    assert len(attempt.signal_lease_token_hash) == 64
    assert attempt.status == "active"
    assert attempt.finished_at is None


@pytest.mark.asyncio
async def test_attempt_acquire_reclaims_only_an_expired_owner() -> None:
    """An unexpired owner blocks takeover; expiry is durably abandoned first."""

    now = datetime(2026, 8, 12, 2, tzinfo=timezone.utc)
    run = _queued_migration_run(now=now)
    active = MigrationRunAttempt(
        migration_run_attempt_uuid=uuid.uuid4(),
        migration_run_uuid=run.migration_run_uuid,
        attempt_number=1,
        acquired_state_version=1,
        status="active",
        worker_identity_hash="a" * 64,
        signal_lease_token_hash="b" * 64,
        lease_expires_at=now + timedelta(seconds=1),
        acquired_at=now - timedelta(seconds=10),
        last_heartbeat_at=now - timedelta(seconds=10),
        finished_at=None,
    )
    token = uuid.uuid4()
    blocked_session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[run, active]), add=Mock()
    )
    with pytest.raises(MigrationRunContractError, match="already active"):
        await acquire_migration_run_attempt(
            blocked_session,
            migration_run_uuid=run.migration_run_uuid,
            worker_identity="worker-b",
            signal_lease_token=token,
            lease_seconds=60,
            now=now,
        )
    blocked_session.add.assert_not_called()

    active.lease_expires_at = now
    reclaim_session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[run, active, 1]), add=Mock()
    )
    claim = await acquire_migration_run_attempt(
        reclaim_session,
        migration_run_uuid=run.migration_run_uuid,
        worker_identity="worker-b",
        signal_lease_token=token,
        lease_seconds=60,
        now=now,
    )
    assert active.status == "abandoned"
    assert active.finished_at == now
    assert claim.attempt_number == 2


@pytest.mark.asyncio
async def test_attempt_renewal_and_finish_are_exact_claim_cas() -> None:
    """Heartbeat and finish require the exact active attempt and hashed owner."""

    now = datetime(2026, 8, 12, 2, tzinfo=timezone.utc)
    claim = MigrationRunAttemptClaim(
        migration_run_attempt_uuid=uuid.uuid4(),
        migration_run_uuid=uuid.uuid4(),
        attempt_number=2,
        acquired_state_version=3,
        lease_expires_at=now + timedelta(seconds=60),
    )
    token = uuid.uuid4()
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(rowcount=1))
    )

    assert await renew_migration_run_attempt(
        session,
        claim=claim,
        worker_identity="worker-a",
        signal_lease_token=token,
        lease_seconds=60,
        now=now,
    ) is True
    renewal = str(
        session.execute.await_args.args[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "migration_run_attempt.status = 'active'" in renewal
    assert "migration_run_attempt.lease_expires_at >" in renewal
    assert "migration_run.cancellation_requested IS false" in renewal
    assert "greatest(" in renewal.lower()
    assert "worker-a" not in renewal
    assert str(token) not in renewal

    session.execute.return_value = SimpleNamespace(rowcount=1)
    assert await finish_migration_run_attempt(
        session,
        claim=claim,
        worker_identity="worker-a",
        signal_lease_token=token,
        succeeded=True,
        now=now,
    ) is True
    finish = str(
        session.execute.await_args.args[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "migration_run_attempt.status = 'active'" in finish
    assert "migration_run_attempt.lease_expires_at >" in finish
    assert "status='completed'" in finish.replace(" ", "")
    assert "finished_at=" in finish

    session.execute.return_value = SimpleNamespace(rowcount=0)
    assert await renew_migration_run_attempt(
        session,
        claim=claim,
        worker_identity="worker-a",
        signal_lease_token=uuid.uuid4(),
        lease_seconds=60,
        now=now,
    ) is False
    assert await finish_migration_run_attempt(
        session,
        claim=claim,
        worker_identity="worker-a",
        signal_lease_token=uuid.uuid4(),
        succeeded=False,
        now=now,
    ) is False
    with pytest.raises(MigrationRunContractError, match="outcome"):
        await finish_migration_run_attempt(
            session,
            claim=claim,
            worker_identity="worker-a",
            signal_lease_token=token,
            succeeded=1,  # type: ignore[arg-type]
            now=now,
        )


@pytest.mark.asyncio
async def test_attempt_contract_rejects_inactive_runs_and_unsafe_inputs() -> None:
    """Terminal/cancelled runs, naive clocks, and unbounded leases fail closed."""

    now = datetime(2026, 8, 12, 2, tzinfo=timezone.utc)
    run = _queued_migration_run(now=now)
    run.cancellation_requested = True
    session = SimpleNamespace(scalar=AsyncMock(return_value=run), add=Mock())
    with pytest.raises(MigrationRunContractError, match="not executable"):
        await acquire_migration_run_attempt(
            session,
            migration_run_uuid=run.migration_run_uuid,
            worker_identity="worker-a",
            signal_lease_token=uuid.uuid4(),
            lease_seconds=60,
            now=now,
        )

    for worker_identity, lease_seconds, expected in (
        ("", 60, "worker identity"),
        ("worker a", 60, "worker identity"),
        ("worker-a", 0, "lease"),
        ("worker-a", 301, "lease"),
    ):
        with pytest.raises(MigrationRunContractError, match=expected):
            await acquire_migration_run_attempt(
                SimpleNamespace(scalar=AsyncMock(), add=Mock()),
                migration_run_uuid=uuid.uuid4(),
                worker_identity=worker_identity,
                signal_lease_token=uuid.uuid4(),
                lease_seconds=lease_seconds,
                now=now,
            )

    with pytest.raises(MigrationRunContractError, match="worker identity"):
        await acquire_migration_run_attempt(
            SimpleNamespace(scalar=AsyncMock(), add=Mock()),
            migration_run_uuid=uuid.uuid4(),
            worker_identity=None,  # type: ignore[arg-type]
            signal_lease_token=uuid.uuid4(),
            lease_seconds=60,
            now=now,
        )

    with pytest.raises(MigrationRunContractError, match="signal lease token"):
        await acquire_migration_run_attempt(
            SimpleNamespace(scalar=AsyncMock(), add=Mock()),
            migration_run_uuid=uuid.uuid4(),
            worker_identity="worker-a",
            signal_lease_token=object(),  # type: ignore[arg-type]
            lease_seconds=60,
            now=now,
        )

    with pytest.raises(MigrationRunContractError, match="timezone"):
        await acquire_migration_run_attempt(
            SimpleNamespace(scalar=AsyncMock(), add=Mock()),
            migration_run_uuid=uuid.uuid4(),
            worker_identity="worker-a",
            signal_lease_token=uuid.uuid4(),
            lease_seconds=60,
            now=datetime(2026, 8, 12, 2),
        )


@pytest.mark.asyncio
async def test_dispatch_claim_uses_due_order_and_skip_locked() -> None:
    """A relay claims one due row without blocking a concurrent relay."""

    now = datetime(2026, 8, 11, 4, tzinfo=timezone.utc)
    dispatch = MigrationRunDispatch(
        migration_run_dispatch_uuid=uuid.uuid4(),
        migration_run_uuid=uuid.uuid4(),
        dispatch_kind="isolated_dry_run",
        status="pending",
        attempt_count=0,
        not_before=now,
        created_at=now,
        published_at=None,
    )
    session = SimpleNamespace(scalar=AsyncMock(return_value=dispatch))

    claim = await claim_one_migration_dispatch(session, now=now)

    assert claim == MigrationDispatchClaim(
        migration_run_dispatch_uuid=dispatch.migration_run_dispatch_uuid,
        migration_run_uuid=dispatch.migration_run_uuid,
        dispatch_kind="isolated_dry_run",
        attempt_count=1,
    )
    assert dispatch.attempt_count == 1
    statement = session.scalar.await_args.args[0]
    compiled = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "migration_run_dispatch.status = 'pending'" in compiled
    assert "migration_run_dispatch.not_before <=" in compiled
    assert "ORDER BY migration_run_dispatch.not_before" in compiled
    assert "FOR UPDATE SKIP LOCKED" in compiled


@pytest.mark.asyncio
async def test_dispatch_claim_returns_none_without_mutating_transaction() -> None:
    """An empty due queue remains a no-op owned by the caller transaction."""

    session = SimpleNamespace(scalar=AsyncMock(return_value=None))
    assert await claim_one_migration_dispatch(session) is None


@pytest.mark.asyncio
async def test_dispatch_publish_is_attempt_bound_and_caller_owned() -> None:
    """Publication succeeds only for the exact in-transaction claim attempt."""

    now = datetime(2026, 8, 11, 4, tzinfo=timezone.utc)
    claim = MigrationDispatchClaim(
        migration_run_dispatch_uuid=uuid.uuid4(),
        migration_run_uuid=uuid.uuid4(),
        dispatch_kind="isolated_dry_run",
        attempt_count=2,
    )
    result = SimpleNamespace(rowcount=1)
    session = SimpleNamespace(execute=AsyncMock(return_value=result))

    await mark_migration_dispatch_published(session, claim=claim, now=now)

    statement = session.execute.await_args.args[0]
    compiled = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "migration_run_dispatch.status = 'pending'" in compiled
    assert "migration_run_dispatch.attempt_count = 2" in compiled
    assert "status='published'" in compiled.replace(" ", "")
    assert "published_at=" in compiled

    session.execute.return_value = SimpleNamespace(rowcount=0)
    with pytest.raises(MigrationRunContractError, match="claim is stale"):
        await mark_migration_dispatch_published(session, claim=claim, now=now)


@pytest.mark.asyncio
async def test_dispatch_claim_and_publish_require_timezone_aware_time() -> None:
    """Naive clocks cannot enter durable outbox ordering or evidence."""

    session = SimpleNamespace(scalar=AsyncMock(), execute=AsyncMock())
    naive = datetime(2026, 8, 11, 4)
    with pytest.raises(MigrationRunContractError, match="timezone"):
        await claim_one_migration_dispatch(session, now=naive)
    with pytest.raises(MigrationRunContractError, match="timezone"):
        await mark_migration_dispatch_published(
            session,
            claim=MigrationDispatchClaim(
                migration_run_dispatch_uuid=uuid.uuid4(),
                migration_run_uuid=uuid.uuid4(),
                dispatch_kind="isolated_dry_run",
                attempt_count=1,
            ),
            now=naive,
        )
    session.scalar.assert_not_awaited()
    session.execute.assert_not_awaited()

    with pytest.raises(MigrationRunContractError, match="attempt is invalid"):
        await mark_migration_dispatch_published(
            session,
            claim=MigrationDispatchClaim(
                migration_run_dispatch_uuid=uuid.uuid4(),
                migration_run_uuid=uuid.uuid4(),
                dispatch_kind="isolated_dry_run",
                attempt_count=0,
            ),
            now=datetime(2026, 8, 11, 4, tzinfo=timezone.utc),
        )
    session.execute.assert_not_awaited()


def test_migration_run_alembic_revision_matches_model_contract() -> None:
    """Alembic creates the same durable-run constraints as the ORM contract."""

    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/0010_migration_run.py"
    ).read_text(encoding="utf-8")

    for required in (
        'down_revision = "0009_migration_plan"',
        '"migration_run"',
        '"migration_run_event"',
        '"migration_run_dispatch"',
        '"uq_migration_run_dispatch__migration_run_uuid"',
        '"ck_migration_run_dispatch__dispatch_kind"',
        '"ck_migration_run_dispatch__status"',
        '"ck_migration_run_dispatch__attempt_count"',
        '"ck_migration_run_dispatch__published_at"',
        '"ix_migration_run_dispatch__status_not_before"',
        '"uq_migration_run__idempotent_action"',
        '"request_digest"',
        '"latest_event_digest"',
        '"previous_event_digest"',
        '"event_digest"',
        '"uq_migration_run_event__run_sequence"',
        '"ck_migration_run__state_version"',
        '"ck_migration_run__latest_event_digest"',
        '"ck_migration_run__idempotency_key_hash"',
        '"ck_migration_run__plan_digest"',
        '"ck_migration_run__request_digest"',
        '"ck_migration_run__observed_base_digest"',
        '"ck_migration_run_event__previous_digest_format"',
        '"ck_migration_run_event__event_digest"',
        '"ck_migration_run_event__event_type"',
        '"ck_migration_run_event__state_before"',
        '"ck_migration_run_event__state_after"',
        '"ck_migration_run__kind_state"',
        'ondelete="RESTRICT"',
        'ondelete="CASCADE"',
    ):
        assert required in migration

    attempt_migration = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/0011_migration_run_attempt.py"
    ).read_text(encoding="utf-8")
    for required in (
        'down_revision = "0010_migration_run"',
        '"migration_run_attempt"',
        '"uq_migration_run_attempt__run_number"',
        '"ck_migration_run_attempt__attempt_number"',
        '"ck_migration_run_attempt__acquired_state_version"',
        '"ck_migration_run_attempt__status"',
        '"ck_migration_run_attempt__worker_identity_hash"',
        '"ck_migration_run_attempt__signal_lease_token_hash"',
        '"ck_migration_run_attempt__timestamps"',
        '"ix_migration_run_attempt__active_run"',
        '"ix_migration_run_attempt__lease_expiry"',
        'postgresql_where=sa.text("status = \'active\'")',
        'ondelete="CASCADE"',
    ):
        assert required in attempt_migration


@pytest.mark.asyncio
async def test_transition_uses_optimistic_cas_and_appends_sanitized_event() -> None:
    """A successful transition updates one exact version and appends its event."""

    run_uuid = uuid.uuid4()
    actor_uuid = uuid.uuid4()
    run = MigrationRun(
        migration_run_uuid=run_uuid,
        project_space_uuid=uuid.uuid4(),
        migration_plan_uuid=uuid.uuid4(),
        run_kind="dry_run",
        state="queued",
        state_version=1,
        idempotency_key_hash="a" * 64,
        plan_digest="b" * 64,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=actor_uuid,
        cancellation_requested=False,
        evidence_json={},
    )
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=run),
        execute=AsyncMock(return_value=SimpleNamespace(rowcount=1)),
        add=Mock(),
    )
    now = datetime(2026, 8, 10, tzinfo=timezone.utc)

    result = await transition_migration_run(
        session,
        migration_run_uuid=run_uuid,
        expected_state_version=1,
        next_state="sandbox_running",
        event_type="sandbox_started",
        evidence={"sandbox_version": "postgresql-18", "attempt": 1},
        actor_user_uuid=actor_uuid,
        now=now,
    )

    statement = session.execute.await_args.args[0]
    compiled = statement.compile()
    assert {
        "migration_run_uuid_1",
        "state_version_1",
        "state_1",
    }.issubset(compiled.params)
    assert compiled.params["migration_run_uuid_1"] == run_uuid
    assert compiled.params["state_version_1"] == 1
    assert compiled.params["state_1"] == "queued"
    event = session.add.call_args.args[0]
    assert isinstance(event, MigrationRunEvent)
    assert event.sequence_number == 2
    assert event.state_before == "queued"
    assert event.state_after == "sandbox_running"
    assert event.evidence_json == {
        "attempt": 1,
        "sandbox_version": "postgresql-18",
    }
    assert event.previous_event_digest == "d" * 64
    assert event.event_digest == digest_run_event(
        migration_run_uuid=run_uuid,
        sequence_number=2,
        event_type="sandbox_started",
        state_before="queued",
        state_after="sandbox_running",
        evidence=event.evidence_json,
        actor_user_uuid=actor_uuid,
        created_at=now,
        previous_event_digest="d" * 64,
    )
    assert result.state == "sandbox_running"
    assert result.state_version == 2
    assert result.started_at == now
    assert result.finished_at is None
    assert run.state == "sandbox_running"
    assert run.state_version == 2
    assert run.evidence_json == event.evidence_json
    assert run.latest_event_digest == event.event_digest
    assert run.updated_at == now
    assert run.started_at == now
    assert run.finished_at is None


@pytest.mark.asyncio
async def test_transition_fails_closed_when_compare_and_swap_loses_race() -> None:
    """A stale worker cannot append evidence after losing the state-version CAS."""

    run = MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        migration_plan_uuid=uuid.uuid4(),
        run_kind="dry_run",
        state="queued",
        state_version=2,
        idempotency_key_hash="a" * 64,
        plan_digest="b" * 64,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=uuid.uuid4(),
        cancellation_requested=False,
        evidence_json={},
    )
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=run),
        execute=AsyncMock(return_value=SimpleNamespace(rowcount=0)),
        add=Mock(),
    )

    with pytest.raises(MigrationRunContractError, match="state version conflict"):
        await transition_migration_run(
            session,
            migration_run_uuid=run.migration_run_uuid,
            expected_state_version=2,
            next_state="sandbox_running",
            event_type="sandbox_started",
            evidence={},
            actor_user_uuid=None,
        )

    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_preflight_terminal_transition_binds_observed_base_digest() -> None:
    """Passed evidence persists only the exact base observed by preflight."""

    plan = _migration_plan()
    run = MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=plan.project_space_uuid,
        migration_plan_uuid=plan.migration_plan_uuid,
        run_kind="dry_run",
        state="live_preflight_running",
        state_version=3,
        idempotency_key_hash="a" * 64,
        plan_digest=plan.statement_digest,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=uuid.uuid4(),
        cancellation_requested=False,
        evidence_json={},
    )
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[run, plan]),
        execute=AsyncMock(return_value=SimpleNamespace(rowcount=1)),
        add=Mock(),
    )

    result = await transition_migration_run(
        session,
        migration_run_uuid=run.migration_run_uuid,
        expected_state_version=3,
        next_state="passed",
        event_type="preflight_passed",
        evidence={"finding_count": 0},
        observed_base_digest=plan.base_digest,
        actor_user_uuid=None,
    )

    assert result.state == "passed"
    assert run.observed_base_digest == plan.base_digest
    event = session.add.call_args.args[0]
    assert event.evidence_json == {
        "finding_count": 0,
        "observed_base_digest": plan.base_digest,
    }


@pytest.mark.asyncio
async def test_preflight_drift_transition_persists_mismatched_base_digest() -> None:
    """Drift evidence persists only a canonical digest unequal to the plan base."""

    plan = _migration_plan()
    observed_base_digest = "0" * 64
    assert observed_base_digest != plan.base_digest
    run = MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=plan.project_space_uuid,
        migration_plan_uuid=plan.migration_plan_uuid,
        run_kind="dry_run",
        state="live_preflight_running",
        state_version=3,
        idempotency_key_hash="a" * 64,
        plan_digest=plan.statement_digest,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=uuid.uuid4(),
        cancellation_requested=False,
        evidence_json={},
    )
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[run, plan]),
        execute=AsyncMock(return_value=SimpleNamespace(rowcount=1)),
        add=Mock(),
    )

    result = await transition_migration_run(
        session,
        migration_run_uuid=run.migration_run_uuid,
        expected_state_version=3,
        next_state="drifted",
        event_type="preflight_drifted",
        evidence={},
        observed_base_digest=observed_base_digest,
        actor_user_uuid=None,
    )

    assert result.state == "drifted"
    assert run.observed_base_digest == observed_base_digest
    assert session.add.call_args.args[0].evidence_json == {
        "observed_base_digest": observed_base_digest
    }


@pytest.mark.asyncio
async def test_complete_isolated_dry_run_binds_exact_plan_result_to_cas() -> None:
    """A verified executor result selects one server-authored next state."""

    plan = _migration_plan()
    run = MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=plan.project_space_uuid,
        migration_plan_uuid=plan.migration_plan_uuid,
        run_kind="dry_run",
        state="sandbox_running",
        state_version=2,
        idempotency_key_hash="a" * 64,
        plan_digest=plan.statement_digest,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=uuid.uuid4(),
        cancellation_requested=False,
        evidence_json={},
    )
    executor_result = {
        "postgresql_major": 18,
        "statement_count": 0,
        "base_digest": plan.base_digest,
        "target_digest": plan.target_digest,
        "converged": True,
    }
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[run, plan]))
    transition = AsyncMock(
        return_value=SimpleNamespace(state="live_preflight_running")
    )
    completed_at = datetime(2026, 8, 10, 1, tzinfo=timezone.utc)

    with patch(
        "app.forward.migration_run.transition_migration_run", new=transition
    ):
        completed = await complete_isolated_dry_run(
            session,  # type: ignore[arg-type]
            migration_run_uuid=run.migration_run_uuid,
            expected_state_version=2,
            result=executor_result,
            actor_user_uuid=None,
            now=completed_at,
        )

    assert completed.state == "live_preflight_running"
    transition.assert_awaited_once_with(
        session,
        migration_run_uuid=run.migration_run_uuid,
        expected_state_version=2,
        next_state="live_preflight_running",
        event_type="isolated_dry_run_succeeded",
        evidence={
            "postgresql_major": 18,
            "statement_count": 0,
            "converged": True,
        },
        actor_user_uuid=None,
        now=completed_at,
    )


@pytest.mark.parametrize(
    "result",
    [
        None,
        [],
        {},
        {
            "postgresql_major": True,
            "statement_count": 0,
            "base_digest": "a" * 64,
            "target_digest": "b" * 64,
            "converged": True,
        },
        {
            "postgresql_major": 18,
            "statement_count": -1,
            "base_digest": "a" * 64,
            "target_digest": "b" * 64,
            "converged": True,
        },
        {
            "postgresql_major": 18,
            "statement_count": 1001,
            "base_digest": "a" * 64,
            "target_digest": "b" * 64,
            "converged": True,
        },
        {
            "postgresql_major": 18,
            "statement_count": 0,
            "base_digest": "A" * 64,
            "target_digest": "b" * 64,
            "converged": True,
        },
        {
            "postgresql_major": 18,
            "statement_count": 0,
            "base_digest": "a" * 64,
            "target_digest": "b" * 64,
            "converged": False,
        },
        {
            "postgresql_major": 18,
            "statement_count": 0,
            "base_digest": "a" * 64,
            "target_digest": "b" * 64,
            "converged": True,
            "next_state": "live_preflight_running",
        },
    ],
)
@pytest.mark.asyncio
async def test_complete_isolated_dry_run_rejects_forged_results(
    result: object,
) -> None:
    """Malformed or caller-extended executor results fail before durable I/O."""

    session = SimpleNamespace(scalar=AsyncMock())
    transition = AsyncMock()
    with patch(
        "app.forward.migration_run.transition_migration_run", new=transition
    ), pytest.raises(MigrationRunContractError, match="isolated dry-run result"):
        await complete_isolated_dry_run(
            session,  # type: ignore[arg-type]
            migration_run_uuid=uuid.uuid4(),
            expected_state_version=2,
            result=result,  # type: ignore[arg-type]
            actor_user_uuid=None,
        )

    session.scalar.assert_not_awaited()
    transition.assert_not_awaited()


@pytest.mark.parametrize(
    "mutation",
    [
        {"postgresql_major": 17},
        {"statement_count": 1},
        {"base_digest": "e" * 64},
        {"target_digest": "f" * 64},
    ],
)
@pytest.mark.asyncio
async def test_complete_isolated_dry_run_rejects_result_plan_mismatch(
    mutation: dict[str, object],
) -> None:
    """Executor output cannot be rebound to a different stored plan."""

    plan = _migration_plan()
    run = MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=plan.project_space_uuid,
        migration_plan_uuid=plan.migration_plan_uuid,
        run_kind="dry_run",
        state="sandbox_running",
        state_version=2,
        idempotency_key_hash="a" * 64,
        plan_digest=plan.statement_digest,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=uuid.uuid4(),
        cancellation_requested=False,
        evidence_json={},
    )
    result: dict[str, object] = {
        "postgresql_major": 18,
        "statement_count": 0,
        "base_digest": plan.base_digest,
        "target_digest": plan.target_digest,
        "converged": True,
        **mutation,
    }
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[run, plan]))
    transition = AsyncMock()
    completed_at = datetime(2026, 8, 10, 1, tzinfo=timezone.utc)

    with patch(
        "app.forward.migration_run.transition_migration_run", new=transition
    ), pytest.raises(MigrationRunContractError, match="does not match"):
        await complete_isolated_dry_run(
            session,  # type: ignore[arg-type]
            migration_run_uuid=run.migration_run_uuid,
            expected_state_version=2,
            result=result,
            actor_user_uuid=None,
            now=completed_at,
        )

    transition.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_isolated_dry_run_rejects_unbound_durable_context() -> None:
    """Naive time, absent run, or absent plan cannot produce success evidence."""

    result = {
        "postgresql_major": 18,
        "statement_count": 0,
        "base_digest": "a" * 64,
        "target_digest": "a" * 64,
        "converged": True,
    }
    migration_run_uuid = uuid.uuid4()
    no_io = SimpleNamespace(scalar=AsyncMock())
    with pytest.raises(MigrationRunContractError, match="include a timezone"):
        await complete_isolated_dry_run(
            no_io,  # type: ignore[arg-type]
            migration_run_uuid=migration_run_uuid,
            expected_state_version=2,
            result=result,
            actor_user_uuid=None,
            now=datetime(2026, 8, 10, 1),
        )
    no_io.scalar.assert_not_awaited()

    missing_run = SimpleNamespace(scalar=AsyncMock(return_value=None))
    with pytest.raises(MigrationRunContractError, match="state version conflict"):
        await complete_isolated_dry_run(
            missing_run,  # type: ignore[arg-type]
            migration_run_uuid=migration_run_uuid,
            expected_state_version=2,
            result=result,
            actor_user_uuid=None,
            now=datetime(2026, 8, 10, 1, tzinfo=timezone.utc),
        )

    plan = _migration_plan()
    run = MigrationRun(
        migration_run_uuid=migration_run_uuid,
        project_space_uuid=plan.project_space_uuid,
        migration_plan_uuid=plan.migration_plan_uuid,
        run_kind="dry_run",
        state="sandbox_running",
        state_version=2,
        idempotency_key_hash="a" * 64,
        plan_digest=plan.statement_digest,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=uuid.uuid4(),
        cancellation_requested=False,
        evidence_json={},
    )
    missing_plan = SimpleNamespace(scalar=AsyncMock(side_effect=[run, None]))
    with pytest.raises(MigrationRunContractError, match="plan integrity"):
        await complete_isolated_dry_run(
            missing_plan,  # type: ignore[arg-type]
            migration_run_uuid=migration_run_uuid,
            expected_state_version=2,
            result={
                **result,
                "base_digest": plan.base_digest,
                "target_digest": plan.target_digest,
            },
            actor_user_uuid=None,
            now=datetime(2026, 8, 10, 1, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize(
    "matches_plan_base, check_results, expected_state, expected_digest",
    [
        (True, [True], "passed", "planned"),
        (False, [True], "drifted", "b" * 64),
        (True, [False], "failed", None),
    ],
)
@pytest.mark.asyncio
async def test_complete_live_preflight_derives_the_only_valid_terminal_state(
    matches_plan_base: bool,
    check_results: list[bool],
    expected_state: str,
    expected_digest: str | None,
) -> None:
    """Worker evidence cannot choose its terminal classification or digest."""

    plan = _migration_plan_with_preconditions()
    run_uuid = uuid.uuid4()
    run = MigrationRun(
        migration_run_uuid=run_uuid,
        project_space_uuid=plan.project_space_uuid,
        migration_plan_uuid=plan.migration_plan_uuid,
        run_kind="dry_run",
        state="live_preflight_running",
        state_version=3,
        idempotency_key_hash="a" * 64,
        plan_digest=plan.statement_digest,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=uuid.uuid4(),
        cancellation_requested=False,
        evidence_json={},
    )
    observed_digest = plan.base_digest if matches_plan_base else "b" * 64
    if expected_digest == "planned":
        expected_digest = plan.base_digest
    result = {
        "preconditions_passed": all(check_results),
        "checks": [
            {
                "statement_index": 0,
                "precondition_index": index,
                "kind": "table_is_empty",
                "passed": passed,
            }
            for index, passed in enumerate(check_results)
        ],
        "observed_base_digest": observed_digest,
        "matches_plan_base": matches_plan_base,
    }
    transition = AsyncMock(return_value=SimpleNamespace(state=expected_state))
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[run, plan]))

    with patch(
        "app.forward.migration_run.transition_migration_run", new=transition
    ):
        completed = await complete_live_preflight(
            session,  # type: ignore[arg-type]
            migration_run_uuid=run_uuid,
            expected_state_version=3,
            result=result,
            actor_user_uuid=None,
            now=datetime(2026, 8, 10, 1, tzinfo=timezone.utc),
        )

    assert completed.state == expected_state
    transition.assert_awaited_once_with(
        ANY,
        migration_run_uuid=run_uuid,
        expected_state_version=3,
        next_state=expected_state,
        event_type=f"live_preflight_{expected_state}",
        evidence={
            "check_count": len(check_results),
            "failed_check_count": check_results.count(False),
        },
        observed_base_digest=expected_digest,
        actor_user_uuid=None,
        now=datetime(2026, 8, 10, 1, tzinfo=timezone.utc),
    )


@pytest.mark.parametrize(
    "checks",
    [
        [],
        [
            {
                "statement_index": 0,
                "precondition_index": 0,
                "kind": "no_null_values",
                "passed": True,
            }
        ],
        [
            {
                "statement_index": 0,
                "precondition_index": 0,
                "kind": "table_is_empty",
                "passed": True,
            },
            {
                "statement_index": 0,
                "precondition_index": 1,
                "kind": "table_is_empty",
                "passed": True,
            },
        ],
    ],
)
@pytest.mark.asyncio
async def test_complete_live_preflight_requires_exact_plan_preconditions(
    checks: list[dict[str, object]],
) -> None:
    """Missing, extra, or kind-mismatched check evidence cannot pass."""

    plan = _migration_plan_with_preconditions()
    run = MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=plan.project_space_uuid,
        migration_plan_uuid=plan.migration_plan_uuid,
        run_kind="dry_run",
        state="live_preflight_running",
        state_version=3,
        idempotency_key_hash="a" * 64,
        plan_digest=plan.statement_digest,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=uuid.uuid4(),
        cancellation_requested=False,
        evidence_json={},
    )
    transition = AsyncMock()
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[run, plan]))
    with patch(
        "app.forward.migration_run.transition_migration_run", new=transition
    ), pytest.raises(MigrationRunContractError, match="does not match migration plan"):
        await complete_live_preflight(
            session,  # type: ignore[arg-type]
            migration_run_uuid=run.migration_run_uuid,
            expected_state_version=3,
            result={
                "preconditions_passed": True,
                "checks": checks,
                "observed_base_digest": plan.base_digest,
                "matches_plan_base": True,
            },
            actor_user_uuid=None,
            now=datetime(2026, 8, 10, 1, tzinfo=timezone.utc),
        )

    transition.assert_not_awaited()


@pytest.mark.parametrize(
    "plan_json",
    [
        {},
        {"statements": [None]},
        {"statements": [{}]},
        {"statements": [{"preconditions": [None]}]},
        {"statements": [{"preconditions": [{"kind": None}]}]},
        {"statements": [{"preconditions": [{"kind": "unknown"}]}]},
    ],
)
def test_expected_live_preflight_checks_rejects_malformed_plan_structure(
    plan_json: dict[str, object],
) -> None:
    """Malformed persisted statement/precondition structure fails closed."""

    with pytest.raises(MigrationRunContractError, match="plan integrity"):
        _expected_live_preflight_checks(plan_json)


@pytest.mark.parametrize(
    "invalid_run",
    ["missing", "kind", "state", "version", "cancelled"],
)
@pytest.mark.asyncio
async def test_complete_live_preflight_rejects_invalid_run_authority(
    invalid_run: str,
) -> None:
    """Only the exact active, uncancelled dry-run state may complete."""

    plan = _migration_plan_with_preconditions()
    run = MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=plan.project_space_uuid,
        migration_plan_uuid=plan.migration_plan_uuid,
        run_kind="dry_run",
        state="live_preflight_running",
        state_version=3,
        idempotency_key_hash="a" * 64,
        plan_digest=plan.statement_digest,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=uuid.uuid4(),
        cancellation_requested=False,
        evidence_json={},
    )
    if invalid_run == "kind":
        run.run_kind = "apply"
    elif invalid_run == "state":
        run.state = "sandbox_running"
    elif invalid_run == "version":
        run.state_version = 2
    elif invalid_run == "cancelled":
        run.cancellation_requested = True
    stored_run = None if invalid_run == "missing" else run
    session = SimpleNamespace(scalar=AsyncMock(return_value=stored_run))

    with pytest.raises(MigrationRunContractError, match="state version conflict"):
        await complete_live_preflight(
            session,  # type: ignore[arg-type]
            migration_run_uuid=run.migration_run_uuid,
            expected_state_version=3,
            result={
                "preconditions_passed": True,
                "checks": [
                    {
                        "statement_index": 0,
                        "precondition_index": 0,
                        "kind": "table_is_empty",
                        "passed": True,
                    }
                ],
                "observed_base_digest": plan.base_digest,
                "matches_plan_base": True,
            },
            actor_user_uuid=None,
            now=datetime(2026, 8, 10, 1, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize(
    "invalid_plan",
    [
        "missing",
        "project",
        "run_digest",
        "expired",
        "content_digest",
        "compiler",
        "base_digest",
        "target_digest",
    ],
)
@pytest.mark.asyncio
async def test_complete_live_preflight_rejects_invalid_plan_authority(
    invalid_plan: str,
) -> None:
    """Every stored-plan authority binding is rechecked before completion."""

    plan = _migration_plan_with_preconditions()
    run = MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=plan.project_space_uuid,
        migration_plan_uuid=plan.migration_plan_uuid,
        run_kind="dry_run",
        state="live_preflight_running",
        state_version=3,
        idempotency_key_hash="a" * 64,
        plan_digest=plan.statement_digest,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=uuid.uuid4(),
        cancellation_requested=False,
        evidence_json={},
    )
    if invalid_plan == "project":
        plan.project_space_uuid = uuid.uuid4()
    elif invalid_plan == "run_digest":
        run.plan_digest = "0" * 64
    elif invalid_plan == "expired":
        plan.expires_at = datetime(2026, 8, 10, tzinfo=timezone.utc)
    elif invalid_plan == "content_digest":
        plan.plan_json = {**plan.plan_json, "plan_digest": "0" * 64}
    elif invalid_plan == "compiler":
        plan.compiler_version = "unknown"
    elif invalid_plan == "base_digest":
        plan.base_digest = "0" * 64
    elif invalid_plan == "target_digest":
        plan.target_digest = "0" * 64
    stored_plan = None if invalid_plan == "missing" else plan
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[run, stored_plan]))

    with pytest.raises(MigrationRunContractError, match="plan integrity"):
        await complete_live_preflight(
            session,  # type: ignore[arg-type]
            migration_run_uuid=run.migration_run_uuid,
            expected_state_version=3,
            result={
                "preconditions_passed": True,
                "checks": [
                    {
                        "statement_index": 0,
                        "precondition_index": 0,
                        "kind": "table_is_empty",
                        "passed": True,
                    }
                ],
                "observed_base_digest": plan.base_digest,
                "matches_plan_base": True,
            },
            actor_user_uuid=None,
            now=datetime(2026, 8, 10, 1, tzinfo=timezone.utc),
        )


@pytest.mark.asyncio
async def test_complete_live_preflight_rejects_naive_transition_time() -> None:
    """A timezone-free completion clock fails before durable state access."""

    plan = _migration_plan_with_preconditions()
    session = SimpleNamespace(scalar=AsyncMock())
    with pytest.raises(MigrationRunContractError, match="include a timezone"):
        await complete_live_preflight(
            session,  # type: ignore[arg-type]
            migration_run_uuid=uuid.uuid4(),
            expected_state_version=3,
            result={
                "preconditions_passed": True,
                "checks": [
                    {
                        "statement_index": 0,
                        "precondition_index": 0,
                        "kind": "table_is_empty",
                        "passed": True,
                    }
                ],
                "observed_base_digest": plan.base_digest,
                "matches_plan_base": True,
            },
            actor_user_uuid=None,
            now=datetime(2026, 8, 10, 1),
        )

    session.scalar.assert_not_awaited()


@pytest.mark.parametrize(
    "result",
    [
        None,
        [],
        {},
        {
            "preconditions_passed": True,
            "checks": [],
            "observed_base_digest": "A" * 64,
            "matches_plan_base": True,
        },
        {
            "preconditions_passed": False,
            "checks": [],
            "observed_base_digest": "a" * 64,
            "matches_plan_base": True,
        },
        {
            "preconditions_passed": True,
            "checks": [{"passed": True}],
            "observed_base_digest": "a" * 64,
            "matches_plan_base": True,
        },
        {
            "preconditions_passed": True,
            "checks": [
                {
                    "statement_index": -1,
                    "precondition_index": 0,
                    "kind": "table_is_empty",
                    "passed": True,
                }
            ],
            "observed_base_digest": "a" * 64,
            "matches_plan_base": True,
        },
        {
            "preconditions_passed": True,
            "checks": [
                {
                    "statement_index": 0,
                    "precondition_index": 0,
                    "kind": [],
                    "passed": True,
                }
            ],
            "observed_base_digest": "a" * 64,
            "matches_plan_base": True,
        },
        {
            "preconditions_passed": True,
            "checks": [
                {
                    "statement_index": 0,
                    "precondition_index": 0,
                    "kind": "table_is_empty",
                    "passed": True,
                },
                {
                    "statement_index": 0,
                    "precondition_index": 0,
                    "kind": "no_null_values",
                    "passed": True,
                },
            ],
            "observed_base_digest": "a" * 64,
            "matches_plan_base": True,
        },
        {
            "preconditions_passed": True,
            "checks": [],
            "observed_base_digest": "a" * 64,
            "matches_plan_base": True,
            "next_state": "passed",
        },
    ],
)
@pytest.mark.asyncio
async def test_complete_live_preflight_rejects_incomplete_or_forged_results(
    result: object,
) -> None:
    """Only the exact bounded executor result shape may reach durable CAS."""

    transition = AsyncMock()
    with patch(
        "app.forward.migration_run.transition_migration_run", new=transition
    ), pytest.raises(MigrationRunContractError, match="preflight result"):
        await complete_live_preflight(
            SimpleNamespace(),  # type: ignore[arg-type]
            migration_run_uuid=uuid.uuid4(),
            expected_state_version=3,
            result=result,  # type: ignore[arg-type]
            actor_user_uuid=None,
        )

    transition.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_live_preflight_enforces_the_check_count_ceiling() -> None:
    """Oversized worker results fail before durable state access."""

    result = {
        "preconditions_passed": True,
        "checks": [
            {
                "statement_index": index,
                "precondition_index": 0,
                "kind": "table_is_empty",
                "passed": True,
            }
            for index in range(1001)
        ],
        "observed_base_digest": "a" * 64,
        "matches_plan_base": True,
    }
    transition = AsyncMock()
    with patch(
        "app.forward.migration_run.transition_migration_run", new=transition
    ), pytest.raises(MigrationRunContractError, match="preflight result"):
        await complete_live_preflight(
            SimpleNamespace(),  # type: ignore[arg-type]
            migration_run_uuid=uuid.uuid4(),
            expected_state_version=3,
            result=result,
            actor_user_uuid=None,
        )

    transition.assert_not_awaited()


@pytest.mark.parametrize(
    "evidence",
    [
        {"observed_base_digest": "0" * 64},
        {"observedBaseDigest": "0" * 64},
        {"nested": {"observed-base-digest": "0" * 64}},
        {"nested": [{"observed.base.digest": "0" * 64}]},
    ],
)
@pytest.mark.asyncio
async def test_preflight_terminal_transition_rejects_worker_supplied_digest_evidence(
    evidence: dict[str, object],
) -> None:
    """Only the server argument may author the observed digest audit field."""

    plan = _migration_plan()
    run = MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=plan.project_space_uuid,
        migration_plan_uuid=plan.migration_plan_uuid,
        run_kind="dry_run",
        state="live_preflight_running",
        state_version=3,
        idempotency_key_hash="a" * 64,
        plan_digest=plan.statement_digest,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=uuid.uuid4(),
        cancellation_requested=False,
        evidence_json={},
    )
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[run, plan]),
        execute=AsyncMock(return_value=SimpleNamespace(rowcount=1)),
        add=Mock(),
    )

    with pytest.raises(MigrationRunContractError, match="server-authoritative"):
        await transition_migration_run(
            session,
            migration_run_uuid=run.migration_run_uuid,
            expected_state_version=3,
            next_state="passed",
            event_type="preflight_passed",
            evidence=evidence,
            observed_base_digest=plan.base_digest,
            actor_user_uuid=None,
        )

    session.execute.assert_not_awaited()
    session.add.assert_not_called()


@pytest.mark.parametrize(
    "next_state, observed_base_digest",
    [
        ("passed", None),
        ("passed", "A" * 64),
        ("passed", "0" * 64),
        ("drifted", "planned"),
    ],
)
@pytest.mark.asyncio
async def test_preflight_terminal_transition_rejects_missing_or_conflicting_digest(
    next_state: str, observed_base_digest: str | None
) -> None:
    """A worker cannot misclassify the observed base as passed or drifted."""

    plan = _migration_plan()
    if observed_base_digest == "planned":
        observed_base_digest = plan.base_digest
    run = MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=plan.project_space_uuid,
        migration_plan_uuid=plan.migration_plan_uuid,
        run_kind="dry_run",
        state="live_preflight_running",
        state_version=3,
        idempotency_key_hash="a" * 64,
        plan_digest=plan.statement_digest,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=uuid.uuid4(),
        cancellation_requested=False,
        evidence_json={},
    )
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[run, plan]),
        execute=AsyncMock(),
        add=Mock(),
    )

    with pytest.raises(MigrationRunContractError, match="observed base digest"):
        await transition_migration_run(
            session,
            migration_run_uuid=run.migration_run_uuid,
            expected_state_version=3,
            next_state=next_state,
            event_type=f"preflight_{next_state}",
            evidence={},
            observed_base_digest=observed_base_digest,
            actor_user_uuid=None,
        )

    session.execute.assert_not_awaited()
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_preflight_terminal_transition_rejects_missing_plan_authority() -> None:
    """Terminal evidence cannot bind when its immutable plan is unavailable."""

    run = MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        migration_plan_uuid=uuid.uuid4(),
        run_kind="dry_run",
        state="live_preflight_running",
        state_version=3,
        idempotency_key_hash="a" * 64,
        plan_digest="b" * 64,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=uuid.uuid4(),
        cancellation_requested=False,
        evidence_json={},
    )
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[run, None]),
        execute=AsyncMock(),
        add=Mock(),
    )

    with pytest.raises(MigrationRunContractError, match="plan integrity"):
        await transition_migration_run(
            session,
            migration_run_uuid=run.migration_run_uuid,
            expected_state_version=3,
            next_state="passed",
            event_type="preflight_passed",
            evidence={},
            observed_base_digest="0" * 64,
            actor_user_uuid=None,
        )

    session.execute.assert_not_awaited()
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_transition_marks_terminal_state_without_restarting_run() -> None:
    """A terminal transition preserves start time and records one finish time."""

    started_at = datetime(2026, 8, 10, 1, tzinfo=timezone.utc)
    finished_at = datetime(2026, 8, 10, 2, tzinfo=timezone.utc)
    run = MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        migration_plan_uuid=uuid.uuid4(),
        run_kind="dry_run",
        state="sandbox_running",
        state_version=3,
        idempotency_key_hash="a" * 64,
        plan_digest="b" * 64,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=uuid.uuid4(),
        cancellation_requested=False,
        evidence_json={},
        started_at=started_at,
    )
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=run),
        execute=AsyncMock(return_value=SimpleNamespace(rowcount=1)),
        add=Mock(),
    )

    result = await transition_migration_run(
        session,
        migration_run_uuid=run.migration_run_uuid,
        expected_state_version=3,
        next_state="failed",
        event_type="sandbox_failed",
        evidence={"finding_count": 0},
        actor_user_uuid=None,
        now=finished_at,
    )

    assert result.started_at == started_at
    assert result.finished_at == finished_at
    event = session.add.call_args.args[0]
    assert event.sequence_number == 4
    assert event.state_before == "sandbox_running"
    assert event.state_after == "failed"
    assert run.state == "failed"
    assert run.state_version == 4
    assert run.evidence_json == {"finding_count": 0}
    assert run.latest_event_digest == event.event_digest
    assert run.updated_at == finished_at
    assert run.started_at == started_at
    assert run.finished_at == finished_at


@pytest.mark.asyncio
async def test_non_preflight_transition_rejects_observed_base_digest() -> None:
    """Other state changes cannot inject a target fingerprint into evidence."""

    run = MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        migration_plan_uuid=uuid.uuid4(),
        run_kind="dry_run",
        state="queued",
        state_version=1,
        idempotency_key_hash="a" * 64,
        plan_digest="b" * 64,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=uuid.uuid4(),
        cancellation_requested=False,
        evidence_json={},
    )
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=run),
        execute=AsyncMock(),
        add=Mock(),
    )

    with pytest.raises(MigrationRunContractError, match="not allowed"):
        await transition_migration_run(
            session,
            migration_run_uuid=run.migration_run_uuid,
            expected_state_version=1,
            next_state="sandbox_running",
            event_type="sandbox_started",
            evidence={},
            observed_base_digest="0" * 64,
            actor_user_uuid=None,
        )

    session.execute.assert_not_awaited()
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_transition_validates_event_metadata_before_database_access() -> None:
    """Invalid event metadata cannot reach persistence or durable evidence."""

    session = SimpleNamespace(
        scalar=AsyncMock(),
        execute=AsyncMock(),
        add=Mock(),
    )
    for expected_version, event_type, evidence, now in (
        (0, "sandbox_started", {}, None),
        (True, "sandbox_started", {}, None),
        (1, "contains whitespace", {}, None),
        (1, "sandbox_started", {"rawSql": "DROP TABLE customer_record"}, None),
        (1, "sandbox_started", {}, datetime(2026, 8, 10)),
    ):
        with pytest.raises(MigrationRunContractError):
            await transition_migration_run(
                session,
                migration_run_uuid=uuid.uuid4(),
                expected_state_version=expected_version,
                next_state="sandbox_running",
                event_type=event_type,
                evidence=evidence,
                actor_user_uuid=None,
                now=now,
            )

    session.scalar.assert_not_awaited()
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_transition_masks_missing_stale_and_invalid_state_before_update() -> None:
    """Missing, stale, or graph-invalid runs never execute a durable update."""

    session = SimpleNamespace(
        scalar=AsyncMock(return_value=None),
        execute=AsyncMock(),
        add=Mock(),
    )
    with pytest.raises(MigrationRunContractError, match="state version conflict"):
        await transition_migration_run(
            session,
            migration_run_uuid=uuid.uuid4(),
            expected_state_version=1,
            next_state="sandbox_running",
            event_type="sandbox_started",
            evidence={},
            actor_user_uuid=None,
        )

    run = MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        migration_plan_uuid=uuid.uuid4(),
        run_kind="dry_run",
        state="queued",
        state_version=2,
        idempotency_key_hash="a" * 64,
        plan_digest="b" * 64,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=uuid.uuid4(),
        cancellation_requested=False,
        evidence_json={},
    )
    session.scalar.return_value = run
    with pytest.raises(MigrationRunContractError, match="state version conflict"):
        await transition_migration_run(
            session,
            migration_run_uuid=run.migration_run_uuid,
            expected_state_version=1,
            next_state="sandbox_running",
            event_type="sandbox_started",
            evidence={},
            actor_user_uuid=None,
        )

    run.state_version = 1
    with pytest.raises(MigrationRunContractError, match="invalid transition"):
        await transition_migration_run(
            session,
            migration_run_uuid=run.migration_run_uuid,
            expected_state_version=1,
            next_state="applying",
            event_type="apply_started",
            evidence={},
            actor_user_uuid=None,
        )

    session.execute.assert_not_awaited()
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_dry_run_uses_database_conflict_winner_and_initial_event() -> None:
    """Creation is one PostgreSQL idempotency insert plus sequence-one evidence."""

    now = datetime(2026, 8, 10, 3, tzinfo=timezone.utc)
    plan = _migration_plan()
    actor_uuid = uuid.uuid4()
    run_uuid = uuid.uuid4()
    insert_result = SimpleNamespace(
        scalar_one_or_none=Mock(return_value=run_uuid)
    )
    session = SimpleNamespace(
        execute=AsyncMock(return_value=insert_result),
        scalar=AsyncMock(),
        add=Mock(),
    )

    created = await create_migration_run(
        session,
        plan=plan,
        run_kind="dry_run",
        idempotency_key="browser-request-한글-1",
        requested_by_user_uuid=actor_uuid,
        evidence={"request_source": "review_ui"},
        now=now,
    )

    statement = session.execute.await_args.args[0]
    compiled = str(statement.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT ON CONSTRAINT uq_migration_run__idempotent_action DO NOTHING" in compiled
    assert "RETURNING migration_run.migration_run_uuid" in compiled
    added = [call.args[0] for call in session.add.call_args_list]
    event = next(item for item in added if isinstance(item, MigrationRunEvent))
    dispatch = next(
        item for item in added if isinstance(item, MigrationRunDispatch)
    )
    assert isinstance(event, MigrationRunEvent)
    assert event.migration_run_uuid == run_uuid
    assert event.sequence_number == 1
    assert event.state_before is None
    assert event.state_after == "queued"
    assert event.evidence_json == {"request_source": "review_ui"}
    assert event.previous_event_digest is None
    assert len(event.event_digest) == 64
    assert dispatch.migration_run_uuid == run_uuid
    assert dispatch.dispatch_kind == "isolated_dry_run"
    assert dispatch.status == "pending"
    assert dispatch.attempt_count == 0
    assert dispatch.not_before == now
    assert dispatch.created_at == now
    assert dispatch.published_at is None
    assert created.migration_run_uuid == run_uuid
    assert created.reused is False
    session.scalar.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_apply_intent_binds_passed_run_and_exact_confirmation() -> None:
    """Apply creation persists reviewed evidence but creates no executor dispatch."""

    now = datetime(2026, 8, 10, 3, tzinfo=timezone.utc)
    plan = _migration_plan()
    actor_uuid = uuid.uuid4()
    passed_run = MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=plan.project_space_uuid,
        migration_plan_uuid=plan.migration_plan_uuid,
        run_kind="dry_run",
        state="passed",
        state_version=4,
        idempotency_key_hash="a" * 64,
        plan_digest=plan.statement_digest,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=actor_uuid,
        cancellation_requested=False,
        observed_base_digest=plan.base_digest,
        evidence_json={},
    )
    connection = DbConnection(
        db_connection_uuid=plan.db_connection_uuid,
        project_space_uuid=plan.project_space_uuid,
        conn_name='Production "Primary"',
        dsn_ciphertext=b"ciphertext",
        dsn_nonce=b"nonce",
    )
    revision, model = _current_revision(plan, actor_uuid=actor_uuid)
    run_uuid = uuid.uuid4()
    session = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalar_one_or_none=Mock(return_value=run_uuid)
            )
        ),
        scalar=AsyncMock(),
        add=Mock(),
    )

    created = await create_migration_run(
        session,
        plan=plan,
        run_kind="apply",
        idempotency_key="apply-request-1",
        requested_by_user_uuid=actor_uuid,
        evidence={"request_source": "review_ui"},
        passed_dry_run=passed_run,
        connection=connection,
        typed_connection_name='Production "Primary"',
        destructive_acknowledged=False,
        model_revision=revision,
        schema_model=model,
        now=now,
    )

    statement = session.execute.await_args.args[0]
    params = statement.compile(dialect=postgresql.dialect()).params
    assert params["run_kind"] == "apply"
    assert params["passed_dry_run_uuid"] == passed_run.migration_run_uuid
    assert params["destructive_confirmation"] is False
    assert len(params["confirmation_digest"]) == 64
    added = [call.args[0] for call in session.add.call_args_list]
    event = next(item for item in added if isinstance(item, MigrationRunEvent))
    assert event.evidence_json == {
        "destructive_acknowledged": False,
        "passed_dry_run_uuid": str(passed_run.migration_run_uuid),
        "request_source": "review_ui",
        "target_connection_confirmed": True,
    }
    assert not any(isinstance(item, MigrationRunDispatch) for item in added)
    assert created.migration_run_uuid == run_uuid
    assert created.reused is False


@pytest.mark.asyncio
async def test_create_apply_intent_rejects_unbounded_internal_connection_name() -> None:
    """Non-HTTP callers cannot bypass the typed target-name input bound."""

    plan = _migration_plan()
    actor_uuid = uuid.uuid4()
    passed_run = MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=plan.project_space_uuid,
        migration_plan_uuid=plan.migration_plan_uuid,
        run_kind="dry_run",
        state="passed",
        state_version=4,
        idempotency_key_hash="a" * 64,
        plan_digest=plan.statement_digest,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=actor_uuid,
        cancellation_requested=False,
        observed_base_digest=plan.base_digest,
        evidence_json={},
    )
    connection = DbConnection(
        db_connection_uuid=plan.db_connection_uuid,
        project_space_uuid=plan.project_space_uuid,
        conn_name="x" * 129,
        dsn_ciphertext=b"ciphertext",
        dsn_nonce=b"nonce",
    )
    revision, model = _current_revision(plan, actor_uuid=actor_uuid)
    session = SimpleNamespace(execute=AsyncMock(), scalar=AsyncMock(), add=Mock())

    with pytest.raises(MigrationRunContractError, match="confirmation"):
        await create_migration_run(
            session,
            plan=plan,
            run_kind="apply",
            idempotency_key="apply-request-oversized",
            requested_by_user_uuid=actor_uuid,
            evidence={},
            passed_dry_run=passed_run,
            connection=connection,
            typed_connection_name="x" * 129,
            destructive_acknowledged=False,
            model_revision=revision,
            schema_model=model,
            now=datetime(2026, 8, 10, 3, tzinfo=timezone.utc),
        )

    session.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("connection_project", "target connection confirmation mismatch"),
        ("passed_plan", "passed dry run is invalid"),
        ("passed_cancelled", "passed dry run is invalid"),
        ("passed_base", "passed dry run is invalid"),
        ("destructive", "destructive confirmation mismatch"),
        ("reserved_evidence", "apply evidence is invalid"),
        ("stale_revision", "migration model revision is stale"),
    ],
)
async def test_create_apply_intent_rejects_every_cross_authority_binding(
    mutation: str, message: str
) -> None:
    """No mismatched target, evidence, or confirmation can reach insertion."""

    plan = _migration_plan()
    actor_uuid = uuid.uuid4()
    passed_run = MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=plan.project_space_uuid,
        migration_plan_uuid=plan.migration_plan_uuid,
        run_kind="dry_run",
        state="passed",
        state_version=4,
        idempotency_key_hash="a" * 64,
        plan_digest=plan.statement_digest,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=actor_uuid,
        cancellation_requested=False,
        observed_base_digest=plan.base_digest,
        evidence_json={},
    )
    connection = DbConnection(
        db_connection_uuid=plan.db_connection_uuid,
        project_space_uuid=plan.project_space_uuid,
        conn_name="Production Primary",
        dsn_ciphertext=b"ciphertext",
        dsn_nonce=b"nonce",
    )
    revision, model = _current_revision(plan, actor_uuid=actor_uuid)
    destructive_acknowledged = False
    evidence: dict[str, object] = {}
    if mutation == "connection_project":
        connection.project_space_uuid = uuid.uuid4()
    elif mutation == "passed_plan":
        passed_run.migration_plan_uuid = uuid.uuid4()
    elif mutation == "passed_cancelled":
        passed_run.cancellation_requested = True
    elif mutation == "passed_base":
        passed_run.observed_base_digest = "e" * 64
    elif mutation == "destructive":
        destructive_acknowledged = True
    elif mutation == "stale_revision":
        model.current_revision_number += 1
    else:
        evidence = {"targetConnectionConfirmed": True}
    session = SimpleNamespace(execute=AsyncMock(), scalar=AsyncMock(), add=Mock())

    with pytest.raises(MigrationRunContractError, match=message):
        await create_migration_run(
            session,
            plan=plan,
            run_kind="apply",
            idempotency_key=f"apply-request-{mutation}",
            requested_by_user_uuid=actor_uuid,
            evidence=evidence,
            passed_dry_run=passed_run,
            connection=connection,
            typed_connection_name=connection.conn_name,
            destructive_acknowledged=destructive_acknowledged,
            model_revision=revision,
            schema_model=model,
            now=datetime(2026, 8, 10, 3, tzinfo=timezone.utc),
        )

    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_dry_run_reuses_only_the_same_effective_request() -> None:
    """A duplicate key reuses the winner only when its request digest matches."""

    now = datetime(2026, 8, 10, 3, tzinfo=timezone.utc)
    plan = _migration_plan()
    actor_uuid = uuid.uuid4()
    existing = MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=plan.project_space_uuid,
        migration_plan_uuid=plan.migration_plan_uuid,
        run_kind="dry_run",
        state="queued",
        state_version=1,
        idempotency_key_hash=hash_idempotency_key("same-key"),
        plan_digest=plan.statement_digest,
        request_digest=digest_run_request(
            project_space_uuid=plan.project_space_uuid,
            migration_plan_uuid=plan.migration_plan_uuid,
            run_kind="dry_run",
            plan_digest=plan.statement_digest,
            requested_by_user_uuid=actor_uuid,
        ),
        latest_event_digest="d" * 64,
        requested_by_user_uuid=actor_uuid,
        cancellation_requested=True,
        evidence_json={},
    )
    session = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(
                scalar_one_or_none=Mock(return_value=None)
            )
        ),
        scalar=AsyncMock(return_value=existing),
        add=Mock(),
    )

    reused = await create_migration_run(
        session,
        plan=plan,
        run_kind="dry_run",
        idempotency_key="same-key",
        requested_by_user_uuid=actor_uuid,
        evidence={},
        now=now,
    )
    assert reused.migration_run_uuid == existing.migration_run_uuid
    assert reused.reused is True
    assert reused.cancellation_requested is True
    session.add.assert_not_called()

    existing.request_digest = "f" * 64
    with pytest.raises(MigrationRunContractError, match="idempotency key conflict"):
        await create_migration_run(
            session,
            plan=plan,
            run_kind="dry_run",
            idempotency_key="same-key",
            requested_by_user_uuid=actor_uuid,
            evidence={},
            now=now,
        )

    existing.request_digest = digest_run_request(
        project_space_uuid=plan.project_space_uuid,
        migration_plan_uuid=plan.migration_plan_uuid,
        run_kind="dry_run",
        plan_digest=plan.statement_digest,
        requested_by_user_uuid=actor_uuid,
    )
    session.scalar.return_value = None
    with pytest.raises(MigrationRunContractError, match="winner is unavailable"):
        await create_migration_run(
            session,
            plan=plan,
            run_kind="dry_run",
            idempotency_key="same-key",
            requested_by_user_uuid=actor_uuid,
            evidence={},
            now=now,
        )


@pytest.mark.asyncio
async def test_create_dry_run_rejects_unexecutable_or_expired_plan_before_insert() -> None:
    """Run creation fails closed for apply, expiry, blockers, or plan tampering."""

    now = datetime(2026, 8, 10, 3, tzinfo=timezone.utc)
    actor_uuid = uuid.uuid4()
    session = SimpleNamespace(execute=AsyncMock(), scalar=AsyncMock(), add=Mock())

    apply_plan = _migration_plan()
    with pytest.raises(MigrationRunContractError, match="dry-run confirmation"):
        await create_migration_run(
            session,
            plan=apply_plan,
            run_kind="dry_run",
            idempotency_key="dry-run-with-confirmation",
            requested_by_user_uuid=actor_uuid,
            evidence={},
            typed_connection_name="must-not-be-present",
            now=now,
        )

    with pytest.raises(MigrationRunContractError, match="apply confirmation"):
        await create_migration_run(
            session,
            plan=apply_plan,
            run_kind="apply",
            idempotency_key="apply-key",
            requested_by_user_uuid=actor_uuid,
            evidence={},
            now=now,
        )

    malformed_confirmation_plan = _migration_plan()
    malformed_confirmation_plan.plan_json = {
        **malformed_confirmation_plan.plan_json,
        "requires_destructive_confirmation": "yes",
    }
    with (
        patch(
            "app.forward.migration_run.verify_migration_plan_digest",
            return_value=True,
        ),
        pytest.raises(MigrationRunContractError, match="apply confirmation"),
    ):
        await create_migration_run(
            session,
            plan=malformed_confirmation_plan,
            run_kind="apply",
            idempotency_key="malformed-confirmation-plan",
            requested_by_user_uuid=actor_uuid,
            evidence={},
            now=now,
        )

    with pytest.raises(MigrationRunContractError, match="run kind"):
        await create_migration_run(
            session,
            plan=apply_plan,
            run_kind="preview",
            idempotency_key="preview-key",
            requested_by_user_uuid=actor_uuid,
            evidence={},
            now=now,
        )
    with pytest.raises(MigrationRunContractError, match="timezone"):
        await create_migration_run(
            session,
            plan=apply_plan,
            run_kind="dry_run",
            idempotency_key="naive-time-key",
            requested_by_user_uuid=actor_uuid,
            evidence={},
            now=datetime(2026, 8, 10, 3),
        )

    expired = _migration_plan(expires_at=now)
    with pytest.raises(MigrationRunContractError, match="expired"):
        await create_migration_run(
            session,
            plan=expired,
            run_kind="dry_run",
            idempotency_key="expired-key",
            requested_by_user_uuid=actor_uuid,
            evidence={},
            now=now,
        )

    blocked = _migration_plan()
    blocked.plan_json = {**blocked.plan_json, "can_dry_run": False}
    with pytest.raises(MigrationRunContractError, match="integrity"):
        await create_migration_run(
            session,
            plan=blocked,
            run_kind="dry_run",
            idempotency_key="blocked-key",
            requested_by_user_uuid=actor_uuid,
            evidence={},
            now=now,
        )

    valid_blocked = _migration_plan(blocked=True)
    with pytest.raises(MigrationRunContractError, match="cannot be dry-run"):
        await create_migration_run(
            session,
            plan=valid_blocked,
            run_kind="dry_run",
            idempotency_key="valid-blocked-key",
            requested_by_user_uuid=actor_uuid,
            evidence={},
            now=now,
        )

    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancellation_intent_uses_cas_and_same_state_event_sequence() -> None:
    """Cancellation increments the durable version without inventing a state."""

    now = datetime(2026, 8, 10, 4, tzinfo=timezone.utc)
    actor_uuid = uuid.uuid4()
    run = MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        migration_plan_uuid=uuid.uuid4(),
        run_kind="dry_run",
        state="sandbox_running",
        state_version=2,
        idempotency_key_hash="a" * 64,
        plan_digest="b" * 64,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=actor_uuid,
        cancellation_requested=False,
        evidence_json={},
    )
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=run),
        execute=AsyncMock(return_value=SimpleNamespace(rowcount=1)),
        add=Mock(),
    )

    result = await request_migration_run_cancellation(
        session,
        migration_run_uuid=run.migration_run_uuid,
        expected_state_version=2,
        actor_user_uuid=actor_uuid,
        evidence={"request_source": "review_ui"},
        now=now,
    )

    statement = session.execute.await_args.args[0]
    compiled = statement.compile()
    assert compiled.params["state_version_1"] == 2
    assert compiled.params["state_1"] == "sandbox_running"
    assert "migration_run.cancellation_requested IS false" in str(compiled)
    event = session.add.call_args.args[0]
    assert event.event_type == "cancellation_requested"
    assert event.sequence_number == 3
    assert event.state_before == event.state_after == "sandbox_running"
    assert event.evidence_json == {"request_source": "review_ui"}
    assert result.state == "sandbox_running"
    assert result.state_version == 3
    assert result.reused is False
    assert run.cancellation_requested is True
    assert run.state_version == 3
    assert run.updated_at == now
    assert run.latest_event_digest == event.event_digest


@pytest.mark.asyncio
async def test_cancellation_is_idempotent_and_rejects_terminal_or_stale_run() -> None:
    """Repeated intent is harmless while terminal and lost-CAS writes fail closed."""

    run = MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        migration_plan_uuid=uuid.uuid4(),
        run_kind="dry_run",
        state="sandbox_running",
        state_version=3,
        idempotency_key_hash="a" * 64,
        plan_digest="b" * 64,
        request_digest="c" * 64,
        latest_event_digest="d" * 64,
        requested_by_user_uuid=uuid.uuid4(),
        cancellation_requested=True,
        evidence_json={},
    )
    session = SimpleNamespace(
        scalar=AsyncMock(return_value=run),
        execute=AsyncMock(return_value=SimpleNamespace(rowcount=0)),
        add=Mock(),
    )
    repeated = await request_migration_run_cancellation(
        session,
        migration_run_uuid=run.migration_run_uuid,
        expected_state_version=3,
        actor_user_uuid=None,
        evidence={},
    )
    assert repeated.reused is True
    session.execute.assert_not_awaited()

    run.cancellation_requested = False
    with pytest.raises(MigrationRunContractError, match="state version conflict"):
        await request_migration_run_cancellation(
            session,
            migration_run_uuid=run.migration_run_uuid,
            expected_state_version=3,
            actor_user_uuid=None,
            evidence={},
        )

    run.state = "passed"
    with pytest.raises(MigrationRunContractError, match="terminal"):
        await request_migration_run_cancellation(
            session,
            migration_run_uuid=run.migration_run_uuid,
            expected_state_version=3,
            actor_user_uuid=None,
            evidence={},
        )

    run.state = "unknown"
    with pytest.raises(MigrationRunContractError, match="state is invalid"):
        await request_migration_run_cancellation(
            session,
            migration_run_uuid=run.migration_run_uuid,
            expected_state_version=3,
            actor_user_uuid=None,
            evidence={},
        )

    run.run_kind = "preview"
    run.state = "queued"
    with pytest.raises(MigrationRunContractError, match="state is invalid"):
        await request_migration_run_cancellation(
            session,
            migration_run_uuid=run.migration_run_uuid,
            expected_state_version=3,
            actor_user_uuid=None,
            evidence={},
        )

    session.scalar.return_value = None
    with pytest.raises(MigrationRunContractError, match="state version conflict"):
        await request_migration_run_cancellation(
            session,
            migration_run_uuid=uuid.uuid4(),
            expected_state_version=3,
            actor_user_uuid=None,
            evidence={},
        )


@pytest.mark.asyncio
async def test_cancellation_validates_metadata_before_database_access() -> None:
    """Invalid cancellation version, evidence, or time never reaches storage."""

    session = SimpleNamespace(
        scalar=AsyncMock(), execute=AsyncMock(), add=Mock()
    )
    for version, evidence, now in (
        (0, {}, None),
        (True, {}, None),
        (1, {"databaseDsn": "postgresql://secret"}, None),
        (1, {}, datetime(2026, 8, 10, 4)),
    ):
        with pytest.raises(MigrationRunContractError):
            await request_migration_run_cancellation(
                session,
                migration_run_uuid=uuid.uuid4(),
                expected_state_version=version,
                actor_user_uuid=None,
                evidence=evidence,
                now=now,
            )

    session.scalar.assert_not_awaited()
    session.execute.assert_not_awaited()
