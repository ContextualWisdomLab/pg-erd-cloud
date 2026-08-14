"""Durable dry-run worker stage orchestration contract tests."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.jobs.migration_dry_run_worker import (
    IsolatedSandboxExecution,
    IsolatedSandboxRequest,
    LivePreflightExecution,
    LivePreflightRequest,
    MigrationDryRunWorkerError,
    _MigrationDryRunWork,
    make_durable_dry_run_attempt_handler,
)


def _work(
    *, state: str = "sandbox_running", state_version: int = 2
) -> _MigrationDryRunWork:
    """Build deterministic durable dry-run work metadata for stage tests."""

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


@pytest.mark.asyncio
async def test_handler_runs_both_stages_through_capability_leases() -> None:
    """Run sandbox and live-preflight cores through separate exact leases."""

    work = _work()
    sandbox_conn = object()
    live_conn = object()
    sandbox_capture = AsyncMock()
    live_capture = AsyncMock()
    order: list[str] = []
    sandbox_requests: list[IsolatedSandboxRequest] = []
    live_requests: list[LivePreflightRequest] = []

    @asynccontextmanager
    async def sandbox_factory(request):
        sandbox_requests.append(request)
        order.append("sandbox-enter")
        try:
            yield IsolatedSandboxExecution(sandbox_conn, sandbox_capture)
        finally:
            order.append("sandbox-exit")

    @asynccontextmanager
    async def live_factory(request):
        live_requests.append(request)
        order.append("live-enter")
        try:
            yield LivePreflightExecution(live_conn, live_capture)
        finally:
            order.append("live-exit")

    sandbox_result = {
        "postgresql_major": 16,
        "statement_count": 0,
        "base_digest": "a" * 64,
        "target_digest": "b" * 64,
        "converged": True,
    }
    preflight_result = {
        "preconditions_passed": True,
        "checks": [],
        "observed_base_digest": "a" * 64,
        "matches_plan_base": True,
    }

    async def execute_sandbox(*args, **kwargs):
        order.append("sandbox-execute")
        assert args == (sandbox_conn, work.plan_json)
        assert kwargs["expected_plan_digest"] == work.plan_digest
        assert kwargs["capture_snapshot"] is sandbox_capture
        return sandbox_result

    async def execute_preflight(*args, **kwargs):
        order.append("live-execute")
        assert args == (live_conn, work.plan_json)
        assert kwargs["capture_snapshot"] is live_capture
        return preflight_result

    async def complete_sandbox(_factory, actual, result):
        order.append("sandbox-complete")
        assert actual == work
        assert result == sandbox_result
        return SimpleNamespace(state="live_preflight_running", state_version=3)

    async def complete_live(_factory, actual, result):
        order.append("live-complete")
        assert actual.state == "live_preflight_running"
        assert result == preflight_result
        return SimpleNamespace(state="passed", state_version=4)

    async def refresh_live(_factory, _claim, actual):
        order.append("live-refresh")
        return actual

    signal_claim = SimpleNamespace(migration_run_uuid=work.migration_run_uuid)
    attempt_claim = SimpleNamespace(
        migration_run_attempt_uuid=work.migration_run_attempt_uuid,
        migration_run_uuid=work.migration_run_uuid,
        attempt_number=work.attempt_number,
        acquired_state_version=1,
    )

    with patch(
        "app.jobs.migration_dry_run_worker._load_and_begin",
        new=AsyncMock(return_value=work),
    ), patch(
        "app.jobs.migration_dry_run_worker.execute_isolated_dry_run",
        new=execute_sandbox,
    ), patch(
        "app.jobs.migration_dry_run_worker.execute_bound_live_preflight",
        new=execute_preflight,
    ), patch(
        "app.jobs.migration_dry_run_worker._complete_isolated_stage",
        new=complete_sandbox,
    ), patch(
        "app.jobs.migration_dry_run_worker._complete_live_stage",
        new=complete_live,
    ), patch(
        "app.jobs.migration_dry_run_worker._refresh_live_stage",
        new=refresh_live,
    ):
        handler = make_durable_dry_run_attempt_handler(
            sandbox_factory, live_factory
        )
        await handler(MagicMock(), signal_claim, attempt_claim)

    assert (
        sandbox_requests[0].migration_run_attempt_uuid
        == work.migration_run_attempt_uuid
    )
    assert (
        live_requests[0].migration_run_attempt_uuid
        == work.migration_run_attempt_uuid
    )
    assert order == [
        "sandbox-enter",
        "sandbox-execute",
        "sandbox-exit",
        "sandbox-complete",
        "live-refresh",
        "live-enter",
        "live-execute",
        "live-exit",
        "live-complete",
    ]
    sandbox_fields = sandbox_requests[0].__dataclass_fields__
    assert "db_connection_uuid" not in sandbox_fields
    assert "target_digest" not in sandbox_fields
    assert "plan_json" not in sandbox_fields
    assert sandbox_requests[0].postgresql_major == work.postgresql_major
    assert sandbox_requests[0].base_digest == work.base_digest
    live_fields = live_requests[0].__dataclass_fields__
    assert live_requests[0].db_connection_uuid == work.db_connection_uuid
    assert live_requests[0].expected_state_version == work.state_version
    assert "postgresql_major" not in live_fields
    assert "base_digest" not in live_fields
    assert "plan_json" not in live_fields


@pytest.mark.asyncio
async def test_handler_resumes_live_preflight_without_replaying_sandbox() -> None:
    """Resume the read-only stage without replaying a completed sandbox."""

    work = _work(state="live_preflight_running", state_version=9)

    def sandbox_factory(_request):
        raise AssertionError("sandbox must not be replayed")

    @asynccontextmanager
    async def live_factory(_request):
        yield LivePreflightExecution(object(), AsyncMock())

    signal_claim = SimpleNamespace(migration_run_uuid=work.migration_run_uuid)
    attempt_claim = SimpleNamespace(
        migration_run_attempt_uuid=work.migration_run_attempt_uuid,
        migration_run_uuid=work.migration_run_uuid,
        attempt_number=work.attempt_number,
        acquired_state_version=9,
    )
    with patch(
        "app.jobs.migration_dry_run_worker._load_and_begin",
        new=AsyncMock(return_value=work),
    ), patch(
        "app.jobs.migration_dry_run_worker._refresh_live_stage",
        new=AsyncMock(return_value=work),
    ), patch(
        "app.jobs.migration_dry_run_worker.execute_bound_live_preflight",
        new=AsyncMock(return_value={"checks": []}),
    ), patch(
        "app.jobs.migration_dry_run_worker._complete_live_stage",
        new=AsyncMock(return_value=SimpleNamespace(state="drifted", state_version=10)),
    ), patch(
        "app.jobs.migration_dry_run_worker.execute_isolated_dry_run",
        new=AsyncMock(),
    ) as sandbox_execute:
        handler = make_durable_dry_run_attempt_handler(sandbox_factory, live_factory)
        await handler(MagicMock(), signal_claim, attempt_claim)
    sandbox_execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_handler_rejects_mismatched_claims_before_metadata_io() -> None:
    """Reject divergent queue and durable-attempt identities before database I/O."""

    session_factory = MagicMock()
    handler = make_durable_dry_run_attempt_handler(MagicMock(), MagicMock())
    with pytest.raises(MigrationDryRunWorkerError, match="claim is invalid"):
        await handler(
            session_factory,
            SimpleNamespace(migration_run_uuid=uuid.uuid4()),
            SimpleNamespace(
                migration_run_uuid=uuid.uuid4(),
                attempt_number=1,
                acquired_state_version=1,
            ),
        )
    session_factory.assert_not_called()


@pytest.mark.asyncio
async def test_sandbox_failure_is_sanitized_and_lease_cleanup_runs() -> None:
    """Close the sandbox lease and discard provider failure details."""

    work = _work()
    cleaned = False

    @asynccontextmanager
    async def sandbox_factory(_request):
        nonlocal cleaned
        try:
            yield IsolatedSandboxExecution(object(), AsyncMock())
        finally:
            cleaned = True

    handler = make_durable_dry_run_attempt_handler(sandbox_factory, MagicMock())
    signal_claim = SimpleNamespace(migration_run_uuid=work.migration_run_uuid)
    attempt_claim = SimpleNamespace(
        migration_run_attempt_uuid=work.migration_run_attempt_uuid,
        migration_run_uuid=work.migration_run_uuid,
        attempt_number=work.attempt_number,
        acquired_state_version=1,
    )
    marker = "opaque sandbox provider detail"
    with patch(
        "app.jobs.migration_dry_run_worker._load_and_begin",
        new=AsyncMock(return_value=work),
    ), patch(
        "app.jobs.migration_dry_run_worker.execute_isolated_dry_run",
        new=AsyncMock(side_effect=RuntimeError(marker)),
    ):
        with pytest.raises(MigrationDryRunWorkerError) as caught:
            await handler(MagicMock(), signal_claim, attempt_claim)
    assert str(caught.value) == "isolated dry-run stage failed"
    assert marker not in repr(caught.value)
    assert caught.value.__cause__ is None
    assert cleaned
