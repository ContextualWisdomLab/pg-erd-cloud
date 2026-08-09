from __future__ import annotations

import uuid
from datetime import datetime, timezone
from math import nan
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql

from app.forward.migration_plan import compile_migration_plan
from app.forward.migration_run import (
    MigrationRunContractError,
    canonicalize_run_evidence,
    create_migration_run,
    digest_run_request,
    hash_idempotency_key,
    transition_migration_run,
    validate_run_transition,
)
from app.models import MigrationPlan, MigrationRun, MigrationRunEvent


def _migration_plan(*, expires_at: datetime | None = None) -> MigrationPlan:
    now = datetime(2026, 8, 10, tzinfo=timezone.utc)
    plan_json = compile_migration_plan(
        {"format_version": 1, "postgresql_major": 18, "schemas": []},
        {"format_version": 1, "postgresql_major": 18, "schemas": []},
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


def test_run_state_machine_separates_dry_run_and_apply_authority() -> None:
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
    assert hash_idempotency_key("retry-한글-1") == hash_idempotency_key(
        "retry-한글-1"
    )
    assert len(hash_idempotency_key("retry-한글-1")) == 64

    for value in ("", "contains\nnewline", "x" * 256):
        with pytest.raises(MigrationRunContractError):
            hash_idempotency_key(value)


def test_run_request_digest_binds_exact_actor_plan_and_intent() -> None:
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
        ("run_kind", "apply"),
        ("plan_digest", "b" * 64),
        ("requested_by_user_uuid", uuid.uuid4()),
    ):
        changed = dict(kwargs)
        changed[field] = value
        assert digest_run_request(**changed) != first

    with pytest.raises(MigrationRunContractError, match="run kind"):
        digest_run_request(**{**kwargs, "run_kind": "preview"})
    with pytest.raises(MigrationRunContractError, match="plan digest"):
        digest_run_request(**{**kwargs, "plan_digest": "not-a-digest"})


def test_run_evidence_rejects_secret_and_sql_bearing_fields_recursively() -> None:
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
    assert MigrationRun.__tablename__ == "migration_run"
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
    assert {constraint.name for constraint in MigrationRun.__table__.constraints if isinstance(constraint, CheckConstraint)} == {
        "ck_migration_run__run_kind",
        "ck_migration_run__state",
        "ck_migration_run__kind_state",
        "ck_migration_run__state_version",
    }

    unique_event_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in MigrationRunEvent.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("migration_run_uuid", "sequence_number") in unique_event_columns
    assert {index.name for index in MigrationRun.__table__.indexes} == {
        "ix_migration_run__migration_plan_uuid",
        "ix_migration_run__project_space_uuid",
        "ix_migration_run__project_state",
    }
    assert {index.name for index in MigrationRunEvent.__table__.indexes} == {
        "ix_migration_run_event__migration_run_uuid"
    }

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
        requested_by_user_uuid=uuid.uuid4(),
        cancellation_requested=False,
        evidence_json={},
    )
    assert run.state == "queued"
    assert "dsn" not in MigrationRun.__table__.columns
    assert "sql" not in MigrationRunEvent.__table__.columns


def test_migration_run_alembic_revision_matches_model_contract() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/0010_migration_run.py"
    ).read_text(encoding="utf-8")

    for required in (
        'down_revision = "0009_migration_plan"',
        '"migration_run"',
        '"migration_run_event"',
        '"uq_migration_run__idempotent_action"',
        '"request_digest"',
        '"uq_migration_run_event__run_sequence"',
        '"ck_migration_run__state_version"',
        '"ck_migration_run__kind_state"',
        'ondelete="RESTRICT"',
        'ondelete="CASCADE"',
    ):
        assert required in migration


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
    assert result.state == "sandbox_running"
    assert result.state_version == 2
    assert result.started_at == now
    assert result.finished_at is None


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
async def test_transition_marks_terminal_state_without_restarting_run() -> None:
    """A terminal transition preserves start time and records one finish time."""

    started_at = datetime(2026, 8, 10, 1, tzinfo=timezone.utc)
    finished_at = datetime(2026, 8, 10, 2, tzinfo=timezone.utc)
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
        next_state="passed",
        event_type="preflight_passed",
        evidence={"finding_count": 0},
        actor_user_uuid=None,
        now=finished_at,
    )

    assert result.started_at == started_at
    assert result.finished_at == finished_at
    event = session.add.call_args.args[0]
    assert event.sequence_number == 4
    assert event.state_before == "live_preflight_running"
    assert event.state_after == "passed"


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
    event = session.add.call_args.args[0]
    assert isinstance(event, MigrationRunEvent)
    assert event.migration_run_uuid == run_uuid
    assert event.sequence_number == 1
    assert event.state_before is None
    assert event.state_after == "queued"
    assert event.evidence_json == {"request_source": "review_ui"}
    assert created.migration_run_uuid == run_uuid
    assert created.reused is False
    session.scalar.assert_not_awaited()


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
        requested_by_user_uuid=actor_uuid,
        cancellation_requested=False,
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


@pytest.mark.asyncio
async def test_create_dry_run_rejects_unexecutable_or_expired_plan_before_insert() -> None:
    """Run creation fails closed for apply, expiry, blockers, or plan tampering."""

    now = datetime(2026, 8, 10, 3, tzinfo=timezone.utc)
    actor_uuid = uuid.uuid4()
    session = SimpleNamespace(execute=AsyncMock(), scalar=AsyncMock(), add=Mock())

    apply_plan = _migration_plan()
    with pytest.raises(MigrationRunContractError, match="apply run creation"):
        await create_migration_run(
            session,
            plan=apply_plan,
            run_kind="apply",
            idempotency_key="apply-key",
            requested_by_user_uuid=actor_uuid,
            evidence={},
            now=now,
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

    session.execute.assert_not_awaited()
