from __future__ import annotations

import datetime as dt
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.jobs.migration_dry_run_worker import (
    MigrationDryRunWorkerError,
    _MigrationDryRunWork,
    _make_work,
)


def _work(
    *, state: str = "sandbox_running", state_version: int = 2
) -> _MigrationDryRunWork:
    return _MigrationDryRunWork(
        migration_run_uuid=uuid.uuid4(),
        migration_plan_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        db_connection_uuid=uuid.uuid4(),
        base_schema_snapshot_uuid=uuid.uuid4(),
        migration_run_attempt_uuid=uuid.uuid4(),
        attempt_number=3,
        state=state,
        state_version=state_version,
        postgresql_major=16,
        base_digest="a" * 64,
        target_digest="b" * 64,
        plan_digest="c" * 64,
        plan_json={"statements": []},
    )


def test_make_work_rejects_tampered_or_cancelled_metadata() -> None:
    """Reject cancelled or integrity-invalid durable metadata."""

    run_uuid = uuid.uuid4()
    plan_uuid = uuid.uuid4()
    project_uuid = uuid.uuid4()
    plan_digest = "c" * 64
    now = dt.datetime(2026, 8, 12, tzinfo=dt.timezone.utc)
    run = SimpleNamespace(
        migration_run_uuid=run_uuid,
        project_space_uuid=project_uuid,
        migration_plan_uuid=plan_uuid,
        run_kind="dry_run",
        state="sandbox_running",
        state_version=2,
        plan_digest=plan_digest,
        cancellation_requested=False,
    )
    plan = SimpleNamespace(
        migration_plan_uuid=plan_uuid,
        project_space_uuid=project_uuid,
        db_connection_uuid=uuid.uuid4(),
        base_schema_snapshot_uuid=uuid.uuid4(),
        statement_digest=plan_digest,
        compiler_version="pg-erd-forward/v1",
        base_digest="a" * 64,
        target_digest="b" * 64,
        expires_at=now + dt.timedelta(hours=1),
        plan_json={
            "compiler_version": "pg-erd-forward/v1",
            "postgresql_major": 16,
            "base_digest": "a" * 64,
            "target_digest": "b" * 64,
            "plan_digest": plan_digest,
            "can_dry_run": True,
            "blockers": [],
        },
    )
    claim = SimpleNamespace(
        migration_run_attempt_uuid=uuid.uuid4(),
        migration_run_uuid=run_uuid,
        attempt_number=1,
        acquired_state_version=2,
    )
    with patch(
        "app.jobs.migration_dry_run_worker_contract.verify_migration_plan_digest",
        return_value=True,
    ):
        work = _make_work(run, plan, claim, now=now)
        assert work.plan_json is not plan.plan_json
        run.cancellation_requested = True
        with pytest.raises(MigrationDryRunWorkerError, match="metadata contract"):
            _make_work(run, plan, claim, now=now)


def _transactional_session_factory(*scalar_values: object) -> MagicMock:
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=None)
    transaction.__aexit__ = AsyncMock(return_value=False)
    session.begin.return_value = transaction
    session.scalar = AsyncMock(side_effect=scalar_values)
    factory = MagicMock(return_value=session)
    factory.session = session
    factory.transaction = transaction
    return factory


@pytest.mark.asyncio
async def test_load_and_begin_commits_exact_queued_transition() -> None:
    """Bind the queued transition to the exact durable attempt identity."""

    from app.forward.migration_run import MigrationRunTransition
    from app.jobs.migration_dry_run_worker import _load_and_begin

    work = _work(state="queued", state_version=7)
    run = SimpleNamespace(migration_plan_uuid=work.migration_plan_uuid)
    plan = object()
    factory = _transactional_session_factory(run, plan)
    claim = SimpleNamespace(
        migration_run_attempt_uuid=work.migration_run_attempt_uuid,
        migration_run_uuid=work.migration_run_uuid,
        attempt_number=work.attempt_number,
        acquired_state_version=work.state_version,
    )
    transition = MigrationRunTransition("sandbox_running", 8, None, None)

    query = MagicMock()
    query.where.return_value = query
    query.with_for_update.return_value = query
    with patch(
        "app.jobs.migration_dry_run_worker.select",
        return_value=query,
    ), patch(
        "app.jobs.migration_dry_run_worker._make_work",
        return_value=work,
    ) as make_work, patch(
        "app.jobs.migration_dry_run_worker.transition_migration_run",
        new=AsyncMock(return_value=transition),
    ) as transition_run:
        loaded = await _load_and_begin(factory, claim)

    assert loaded.state == "sandbox_running"
    assert loaded.state_version == 8
    assert factory.call_count == 1
    assert factory.transaction.__aexit__.await_count == 1
    make_work.assert_called_once()
    transition_run.assert_awaited_once()
    kwargs = transition_run.await_args.kwargs
    assert kwargs["migration_run_uuid"] == work.migration_run_uuid
    assert kwargs["expected_state_version"] == 7
    assert kwargs["next_state"] == "sandbox_running"
    assert kwargs["event_type"] == "sandbox_started"
    assert kwargs["evidence"] == {
        "attempt_number": work.attempt_number,
        "migration_run_attempt_uuid": str(work.migration_run_attempt_uuid),
    }
    assert kwargs["actor_user_uuid"] is None
