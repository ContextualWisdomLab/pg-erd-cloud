from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.jobs.migration_dry_run_worker import (
    IsolatedSandboxExecution,
    LivePreflightExecution,
    MigrationDryRunWorkerError,
    _MigrationDryRunWork,
    make_durable_dry_run_attempt_handler,
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


@pytest.mark.asyncio
async def test_handler_propagates_cancellation_and_closes_sandbox_lease() -> None:
    """Propagate lease cancellation while still closing the sandbox capability."""

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
        acquired_state_version=work.state_version,
    )
    with patch(
        "app.jobs.migration_dry_run_worker._load_and_begin",
        new=AsyncMock(return_value=work),
    ), patch(
        "app.jobs.migration_dry_run_worker.execute_isolated_dry_run",
        new=AsyncMock(side_effect=asyncio.CancelledError),
    ):
        with pytest.raises(asyncio.CancelledError):
            await handler(MagicMock(), signal_claim, attempt_claim)
    assert cleaned


@pytest.mark.asyncio
async def test_live_preflight_failure_is_sanitized_and_closes_reader() -> None:
    """Close the target reader and discard read-only provider details."""

    work = _work(state="live_preflight_running", state_version=9)
    cleaned = False

    def sandbox_factory(_request):
        raise AssertionError("sandbox must not run")

    @asynccontextmanager
    async def live_factory(_request):
        nonlocal cleaned
        try:
            yield LivePreflightExecution(object(), AsyncMock())
        finally:
            cleaned = True

    secret = "opaque live provider detail"
    handler = make_durable_dry_run_attempt_handler(sandbox_factory, live_factory)
    signal_claim = SimpleNamespace(migration_run_uuid=work.migration_run_uuid)
    attempt_claim = SimpleNamespace(
        migration_run_attempt_uuid=work.migration_run_attempt_uuid,
        migration_run_uuid=work.migration_run_uuid,
        attempt_number=work.attempt_number,
        acquired_state_version=work.state_version,
    )
    with patch(
        "app.jobs.migration_dry_run_worker._load_and_begin",
        new=AsyncMock(return_value=work),
    ), patch(
        "app.jobs.migration_dry_run_worker._refresh_live_stage",
        new=AsyncMock(return_value=work),
    ), patch(
        "app.jobs.migration_dry_run_worker.execute_bound_live_preflight",
        new=AsyncMock(side_effect=RuntimeError(secret)),
    ):
        with pytest.raises(MigrationDryRunWorkerError) as caught:
            await handler(MagicMock(), signal_claim, attempt_claim)
    assert str(caught.value) == "live preflight stage failed"
    assert secret not in repr(caught.value)
    assert caught.value.__cause__ is None
    assert cleaned


@pytest.mark.asyncio
async def test_handler_rechecks_cancellation_before_live_target_io() -> None:
    """Do not open a target capability after the sandbox stage loses CAS."""

    work = _work()
    live_factory = MagicMock()
    signal_claim = SimpleNamespace(migration_run_uuid=work.migration_run_uuid)
    attempt_claim = SimpleNamespace(
        migration_run_attempt_uuid=work.migration_run_attempt_uuid,
        migration_run_uuid=work.migration_run_uuid,
        attempt_number=work.attempt_number,
        acquired_state_version=work.state_version,
    )

    @asynccontextmanager
    async def sandbox_factory(_request):
        yield IsolatedSandboxExecution(object(), AsyncMock())

    with patch(
        "app.jobs.migration_dry_run_worker._load_and_begin",
        new=AsyncMock(return_value=work),
    ), patch(
        "app.jobs.migration_dry_run_worker.execute_isolated_dry_run",
        new=AsyncMock(return_value={"converged": True}),
    ), patch(
        "app.jobs.migration_dry_run_worker._complete_isolated_stage",
        new=AsyncMock(
            return_value=SimpleNamespace(
                state="live_preflight_running", state_version=3
            )
        ),
    ), patch(
        "app.jobs.migration_dry_run_worker._refresh_live_stage",
        new=AsyncMock(
            side_effect=MigrationDryRunWorkerError(
                "migration dry-run metadata contract is invalid"
            )
        ),
    ):
        handler = make_durable_dry_run_attempt_handler(
            sandbox_factory, live_factory
        )
        with pytest.raises(
            MigrationDryRunWorkerError, match="metadata contract"
        ):
            await handler(MagicMock(), signal_claim, attempt_claim)

    live_factory.assert_not_called()


def test_handler_rejects_unsafe_configuration_before_factory_use() -> None:
    """Reject unsafe timeout and provider configuration before capability use."""

    sandbox_factory = MagicMock()
    live_factory = MagicMock()
    for kwargs, label in (
        ({"lock_timeout_ms": True}, "lock timeout"),
        ({"lock_timeout_ms": 0}, "lock timeout"),
        ({"sandbox_statement_timeout_ms": 0}, "statement timeout"),
        ({"preflight_statement_timeout_ms": 0}, "live-preflight"),
    ):
        with pytest.raises(ValueError, match=label):
            make_durable_dry_run_attempt_handler(
                sandbox_factory, live_factory, **kwargs
            )
    for invalid in (None, 7):
        with pytest.raises(ValueError, match="capability factory"):
            make_durable_dry_run_attempt_handler(
                invalid, live_factory  # type: ignore[arg-type]
            )
        with pytest.raises(ValueError, match="capability factory"):
            make_durable_dry_run_attempt_handler(
                sandbox_factory, invalid  # type: ignore[arg-type]
            )
    sandbox_factory.assert_not_called()
    live_factory.assert_not_called()


@pytest.mark.asyncio
async def test_handler_rejects_invalid_live_terminal_transition() -> None:
    """Reject any terminal state not derived by the live-preflight contract."""

    work = _work(state="live_preflight_running", state_version=4)

    def sandbox_factory(_request):
        raise AssertionError("sandbox must not run")

    @asynccontextmanager
    async def live_factory(_request):
        yield LivePreflightExecution(object(), AsyncMock())

    signal_claim = SimpleNamespace(migration_run_uuid=work.migration_run_uuid)
    attempt_claim = SimpleNamespace(
        migration_run_attempt_uuid=work.migration_run_attempt_uuid,
        migration_run_uuid=work.migration_run_uuid,
        attempt_number=work.attempt_number,
        acquired_state_version=work.state_version,
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
        new=AsyncMock(
            return_value=SimpleNamespace(state="applying", state_version=5)
        ),
    ):
        handler = make_durable_dry_run_attempt_handler(
            sandbox_factory, live_factory
        )
        with pytest.raises(
            MigrationDryRunWorkerError,
            match="live preflight completion is invalid",
        ):
            await handler(MagicMock(), signal_claim, attempt_claim)
