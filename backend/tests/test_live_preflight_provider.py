"""Concrete stored-target live-preflight provider boundary tests."""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.jobs.live_preflight_provider import (
    make_stored_postgres_durable_dry_run_attempt_handler,
    make_stored_postgres_live_preflight_factory,
    make_stored_postgres_migration_run_handler,
)
from app.jobs.migration_dry_run_worker import (
    GuardedLivePreflightTarget,
    LivePreflightExecution,
    LivePreflightRequest,
    MigrationDryRunWorkerError,
)


def _request() -> LivePreflightRequest:
    """Return one exact identifier-only live-preflight request."""

    return LivePreflightRequest(
        migration_run_uuid=uuid.uuid4(),
        migration_plan_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        db_connection_uuid=uuid.uuid4(),
        migration_run_attempt_uuid=uuid.uuid4(),
        attempt_number=2,
        expected_state_version=7,
    )


@pytest.mark.asyncio
async def test_composition_binds_one_metadata_factory_to_provider_and_attempt() -> None:
    """Prevent durable metadata and live-target authority from diverging."""

    session_factory = MagicMock()
    sandbox_factory = MagicMock()
    live_factory = MagicMock()
    delegate = AsyncMock()
    signal_claim = MagicMock()
    attempt_claim = MagicMock()

    with patch(
        "app.jobs.live_preflight_provider."
        "make_stored_postgres_live_preflight_factory",
        return_value=live_factory,
    ) as make_provider, patch(
        "app.jobs.live_preflight_provider."
        "make_durable_dry_run_attempt_handler",
        return_value=delegate,
    ) as make_delegate:
        handler = make_stored_postgres_durable_dry_run_attempt_handler(
            session_factory,
            sandbox_factory,
            preflight_stage_timeout_seconds=12.0,
            connect_timeout_seconds=2.5,
        )
        await handler(session_factory, signal_claim, attempt_claim)

        with pytest.raises(
            MigrationDryRunWorkerError,
            match="migration dry-run composition is invalid",
        ):
            await handler(MagicMock(), signal_claim, attempt_claim)

    make_provider.assert_called_once_with(
        session_factory, connect_timeout_seconds=2.5
    )
    make_delegate.assert_called_once_with(
        sandbox_factory,
        live_factory,
        lock_timeout_ms=1_000,
        sandbox_statement_timeout_ms=30_000,
        preflight_statement_timeout_ms=5_000,
        sandbox_stage_timeout_seconds=300.0,
        preflight_stage_timeout_seconds=12.0,
    )
    delegate.assert_awaited_once_with(
        session_factory, signal_claim, attempt_claim
    )


def test_consumer_composition_binds_attempt_leases_to_stored_provider() -> None:
    """Expose one bounded handler without granting startup or apply authority."""

    session_factory = MagicMock()
    sandbox_factory = MagicMock()
    attempt_handler = MagicMock()
    consumer_handler = MagicMock()

    with patch(
        "app.jobs.live_preflight_provider."
        "make_stored_postgres_durable_dry_run_attempt_handler",
        return_value=attempt_handler,
    ) as make_attempt_handler, patch(
        "app.jobs.live_preflight_provider."
        "make_attempt_bound_migration_run_handler",
        return_value=consumer_handler,
    ) as make_consumer_handler:
        handler = make_stored_postgres_migration_run_handler(
            session_factory,
            sandbox_factory,
            worker_identity="worker-a",
            attempt_lease_seconds=45,
            heartbeat_interval_s=10.0,
            preflight_stage_timeout_seconds=12.0,
            connect_timeout_seconds=2.5,
        )

    assert handler is consumer_handler
    make_attempt_handler.assert_called_once_with(
        session_factory,
        sandbox_factory,
        lock_timeout_ms=1_000,
        sandbox_statement_timeout_ms=30_000,
        preflight_statement_timeout_ms=5_000,
        sandbox_stage_timeout_seconds=300.0,
        preflight_stage_timeout_seconds=12.0,
        connect_timeout_seconds=2.5,
    )
    make_consumer_handler.assert_called_once_with(
        attempt_handler,
        worker_identity="worker-a",
        attempt_lease_seconds=45,
        heartbeat_interval_s=10.0,
    )


@pytest.mark.parametrize(
    "connect_timeout_seconds",
    [0.0, -1.0, float("inf"), float("-inf"), float("nan"), 60.0001],
)
def test_provider_rejects_unbounded_connect_timeout(
    connect_timeout_seconds: float,
) -> None:
    """Keep connection acquisition finite, positive, and operationally bounded."""

    with pytest.raises(ValueError, match="connect timeout"):
        make_stored_postgres_live_preflight_factory(
            MagicMock(), connect_timeout_seconds=connect_timeout_seconds
        )


@pytest.mark.asyncio
async def test_provider_binds_guarded_target_to_same_connection_capture() -> None:
    """Decrypt only guarded material and scope capture to its exact connection."""

    request = _request()
    snapshot_uuid = uuid.uuid4()
    target = GuardedLivePreflightTarget(
        b"encrypted-target",
        b"twelve-bytes",
        snapshot_uuid,
        "tenant$scope",
    )
    metadata_session = object()
    session_context = AsyncMock()
    session_context.__aenter__.return_value = metadata_session
    session_factory = MagicMock(return_value=session_context)
    connection = SimpleNamespace(close=AsyncMock())
    captured = {"snapshot_contract_version": "postgresql/v1"}

    with patch(
        "app.jobs.live_preflight_provider.load_guarded_live_preflight_target",
        new=AsyncMock(return_value=target),
    ) as load_target, patch(
        "app.jobs.live_preflight_provider.decrypt_text",
        return_value="postgresql://user:secret@db.example.test/app",
    ) as decrypt, patch(
        "app.jobs.live_preflight_provider.connect_guarded_postgres",
        new=AsyncMock(return_value=connection),
    ) as connect, patch(
        "app.jobs.live_preflight_provider.capture_postgres_snapshot",
        new=AsyncMock(return_value=captured),
    ) as capture:
        factory = make_stored_postgres_live_preflight_factory(
            session_factory, connect_timeout_seconds=2.5
        )
        async with factory(request) as execution:
            assert isinstance(execution, LivePreflightExecution)
            assert execution.connection is connection
            assert await execution.capture_snapshot(connection) == captured
            with pytest.raises(
                MigrationDryRunWorkerError,
                match="live-preflight capture connection is invalid",
            ):
                await execution.capture_snapshot(object())

    assert load_target.await_count == 2
    load_target.assert_has_awaits(
        [
            ((metadata_session, request),),
            ((metadata_session, request),),
        ]
    )
    decrypt.assert_called_once_with(b"encrypted-target", b"twelve-bytes")
    connect.assert_awaited_once_with(
        "postgresql://user:secret@db.example.test/app", timeout=2.5
    )
    capture.assert_awaited_once_with(connection, "tenant$scope")
    connection.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_provider_revalidates_exact_target_after_connection_open() -> None:
    """Close before reads when guarded metadata changes during acquisition."""

    request = _request()
    snapshot_uuid = uuid.uuid4()
    initial = GuardedLivePreflightTarget(
        b"encrypted-target",
        b"twelve-bytes",
        snapshot_uuid,
        "tenant$scope",
    )
    changed = GuardedLivePreflightTarget(
        b"changed-encrypted-target",
        b"twelve-bytes",
        snapshot_uuid,
        "tenant$scope",
    )
    session_context = AsyncMock()
    session_context.__aenter__.return_value = object()
    session_factory = MagicMock(return_value=session_context)
    connection = SimpleNamespace(close=AsyncMock())

    with patch(
        "app.jobs.live_preflight_provider.load_guarded_live_preflight_target",
        new=AsyncMock(side_effect=(initial, changed)),
    ) as load_target, patch(
        "app.jobs.live_preflight_provider.decrypt_text",
        return_value="postgresql://user:secret@db.example.test/app",
    ), patch(
        "app.jobs.live_preflight_provider.connect_guarded_postgres",
        new=AsyncMock(return_value=connection),
    ), patch(
        "app.jobs.live_preflight_provider.capture_postgres_snapshot",
        new=AsyncMock(),
    ) as capture:
        factory = make_stored_postgres_live_preflight_factory(session_factory)
        with pytest.raises(MigrationDryRunWorkerError) as caught:
            async with factory(request):
                raise AssertionError("changed target must not be yielded")

    assert str(caught.value) == "migration live-preflight provider failed"
    assert load_target.await_count == 2
    capture.assert_not_awaited()
    connection.close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_provider_sanitizes_decrypt_and_connect_failures() -> None:
    """Do not reflect credential or driver detail from acquisition failures."""

    request = _request()
    target = GuardedLivePreflightTarget(
        b"encrypted-secret-marker",
        b"twelve-bytes",
        uuid.uuid4(),
        None,
    )
    session_context = AsyncMock()
    session_context.__aenter__.return_value = object()
    session_factory = MagicMock(return_value=session_context)

    for failing_dependency, failure in (
        ("decrypt_text", ValueError("encrypted-secret-marker")),
        (
            "connect_guarded_postgres",
            RuntimeError("postgresql://user:secret@host/app"),
        ),
    ):
        decrypt = MagicMock(return_value="postgresql://user:secret@host/app")
        connect = AsyncMock(return_value=SimpleNamespace(close=AsyncMock()))
        if failing_dependency == "decrypt_text":
            decrypt.side_effect = failure
        else:
            connect.side_effect = failure
        with patch(
            "app.jobs.live_preflight_provider.load_guarded_live_preflight_target",
            new=AsyncMock(return_value=target),
        ), patch(
            "app.jobs.live_preflight_provider.decrypt_text", new=decrypt
        ), patch(
            "app.jobs.live_preflight_provider.connect_guarded_postgres",
            new=connect,
        ):
            factory = make_stored_postgres_live_preflight_factory(
                session_factory
            )
            with pytest.raises(MigrationDryRunWorkerError) as caught:
                async with factory(request):
                    raise AssertionError("provider must not yield")

        assert str(caught.value) == "migration live-preflight provider failed"
        assert "secret" not in str(caught.value)


@pytest.mark.asyncio
async def test_provider_sanitizes_metadata_context_failures() -> None:
    """Do not reflect a metadata context failure that reuses worker errors."""

    request = _request()
    target = GuardedLivePreflightTarget(
        b"encrypted-target",
        b"twelve-bytes",
        uuid.uuid4(),
        None,
    )
    session_context = AsyncMock()
    session_context.__aenter__.return_value = object()
    session_context.__aexit__.side_effect = MigrationDryRunWorkerError(
        "postgresql://user:secret@metadata.example/app"
    )
    session_factory = MagicMock(return_value=session_context)

    with patch(
        "app.jobs.live_preflight_provider.load_guarded_live_preflight_target",
        new=AsyncMock(return_value=target),
    ), patch(
        "app.jobs.live_preflight_provider.decrypt_text"
    ) as decrypt:
        factory = make_stored_postgres_live_preflight_factory(session_factory)
        with pytest.raises(MigrationDryRunWorkerError) as caught:
            async with factory(request):
                raise AssertionError("provider must not yield")

    assert str(caught.value) == "migration live-preflight provider failed"
    assert "secret" not in str(caught.value)
    decrypt.assert_not_called()


@pytest.mark.asyncio
async def test_provider_propagates_cancellation_and_closes_target() -> None:
    """Preserve process control while closing an acquired target connection."""

    request = _request()
    target = GuardedLivePreflightTarget(
        b"encrypted-target",
        b"twelve-bytes",
        uuid.uuid4(),
        None,
    )
    session_context = AsyncMock()
    session_context.__aenter__.return_value = object()
    session_factory = MagicMock(return_value=session_context)
    connection = SimpleNamespace(close=AsyncMock())

    with patch(
        "app.jobs.live_preflight_provider.load_guarded_live_preflight_target",
        new=AsyncMock(return_value=target),
    ), patch(
        "app.jobs.live_preflight_provider.decrypt_text",
        return_value="postgresql://user:secret@host/app",
    ), patch(
        "app.jobs.live_preflight_provider.connect_guarded_postgres",
        new=AsyncMock(return_value=connection),
    ):
        factory = make_stored_postgres_live_preflight_factory(session_factory)
        with pytest.raises(asyncio.CancelledError):
            async with factory(request):
                raise asyncio.CancelledError

    connection.close.assert_awaited_once_with()
