from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint

from app.forward.migration_run import (
    MigrationRunContractError,
    canonicalize_run_evidence,
    hash_idempotency_key,
    validate_run_transition,
)
from app.models import MigrationRun, MigrationRunEvent


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
    ):
        with pytest.raises(MigrationRunContractError, match="forbidden evidence field"):
            canonicalize_run_evidence(payload)

    with pytest.raises(MigrationRunContractError, match="too large"):
        canonicalize_run_evidence({"detail": "x" * 16_385})


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
        "migration_plan_uuid",
        "run_kind",
        "idempotency_key_hash",
    ) in unique_run_columns
    assert {constraint.name for constraint in MigrationRun.__table__.constraints if isinstance(constraint, CheckConstraint)} == {
        "ck_migration_run__run_kind",
        "ck_migration_run__state",
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
        '"uq_migration_run_event__run_sequence"',
        '"ck_migration_run__state_version"',
        'ondelete="RESTRICT"',
        'ondelete="CASCADE"',
    ):
        assert required in migration
