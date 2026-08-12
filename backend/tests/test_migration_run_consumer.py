"""Execution-neutral migration-run signal consumer contract tests."""

from __future__ import annotations

import asyncio
import datetime as dt
import uuid
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.forward.migration_run import MigrationRunAttemptClaim
from app.jobs.migration_run_consumer import (
    MigrationRunAttemptHandlerError,
    MigrationRunAttemptLeaseLost,
    MigrationRunConsumerError,
    MigrationRunSignalLeaseLost,
    make_attempt_bound_migration_run_handler,
    process_one_migration_run_signal,
    run_migration_run_consumer_forever,
)
from app.jobs.valkey_queue import MigrationRunSignalClaim


def _session_factory() -> AsyncSession:
    """Stand in for the injected metadata-session factory without opening I/O."""

    raise AssertionError("the execution-neutral consumer must not open a session")


def _transactional_session_factory() -> MagicMock:
    """Return fresh recording sessions for durable-attempt transactions."""

    sessions: list[MagicMock] = []
    transactions: list[MagicMock] = []

    def create_session() -> MagicMock:
        session = MagicMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        transaction = MagicMock()
        transaction.__aenter__ = AsyncMock(return_value=None)
        transaction.__aexit__ = AsyncMock(return_value=False)
        session.begin.return_value = transaction
        sessions.append(session)
        transactions.append(transaction)
        return session

    factory = MagicMock(side_effect=create_session)
    factory.sessions = sessions
    factory.transactions = transactions
    return factory


def _attempt_claim(run_uuid: uuid.UUID) -> MigrationRunAttemptClaim:
    return MigrationRunAttemptClaim(
        migration_run_attempt_uuid=uuid.uuid4(),
        migration_run_uuid=run_uuid,
        attempt_number=1,
        acquired_state_version=0,
        lease_expires_at=dt.datetime(2026, 8, 11, 7, 1, tzinfo=dt.timezone.utc),
    )


@pytest.mark.asyncio
async def test_attempt_bound_handler_finishes_exact_success_before_signal_ack() -> None:
    """A handler result is durable only while both exact leases still belong to it."""

    run_uuid = uuid.uuid4()
    signal_claim = MigrationRunSignalClaim(run_uuid, uuid.uuid4())
    attempt_claim = _attempt_claim(run_uuid)
    factory = _transactional_session_factory()

    executor = AsyncMock()

    with patch(
        "app.jobs.migration_run_consumer.acquire_migration_run_attempt",
        new=AsyncMock(return_value=attempt_claim),
    ) as acquire, patch(
        "app.jobs.migration_run_consumer.finish_migration_run_attempt",
        new=AsyncMock(return_value=True),
    ) as finish:
        handler = make_attempt_bound_migration_run_handler(
            executor,
            worker_identity="forward-worker-1",
            attempt_lease_seconds=60,
        )
        await handler(factory, signal_claim)

    acquire.assert_awaited_once_with(
        factory.sessions[0],
        migration_run_uuid=run_uuid,
        worker_identity="forward-worker-1",
        signal_lease_token=signal_claim.lease_token,
        lease_seconds=60,
    )
    executor.assert_awaited_once_with(factory, signal_claim, attempt_claim)
    finish.assert_awaited_once_with(
        factory.sessions[1],
        claim=attempt_claim,
        worker_identity="forward-worker-1",
        signal_lease_token=signal_claim.lease_token,
        succeeded=True,
    )
    assert factory.call_count == 2
    assert all(tx.__aexit__.await_count == 1 for tx in factory.transactions)


@pytest.mark.asyncio
async def test_composed_consumer_acks_only_after_durable_attempt_completion() -> None:
    """The outer signal cannot be acknowledged before exact DB completion."""

    run_uuid = uuid.uuid4()
    signal_claim = MigrationRunSignalClaim(run_uuid, uuid.uuid4())
    attempt_claim = _attempt_claim(run_uuid)
    factory = _transactional_session_factory()
    order: list[str] = []

    async def executor(*_args: object) -> None:
        order.append("executed")

    async def finish(*_args: object, **_kwargs: object) -> bool:
        order.append("attempt-finished")
        return True

    async def ack(actual_claim: MigrationRunSignalClaim) -> bool:
        assert actual_claim == signal_claim
        order.append("signal-acked")
        return True

    with patch(
        "app.jobs.migration_run_consumer.claim_due_migration_run_signal",
        new=AsyncMock(return_value=signal_claim),
    ), patch(
        "app.jobs.migration_run_consumer.acquire_migration_run_attempt",
        new=AsyncMock(return_value=attempt_claim),
    ), patch(
        "app.jobs.migration_run_consumer.finish_migration_run_attempt",
        new=finish,
    ), patch(
        "app.jobs.migration_run_consumer.ack_migration_run_signal",
        new=ack,
    ), patch(
        "app.jobs.migration_run_consumer.release_migration_run_signal",
        new=AsyncMock(),
    ) as release:
        handler = make_attempt_bound_migration_run_handler(
            executor,
            worker_identity="forward-worker-1",
            attempt_lease_seconds=60,
        )
        assert await process_one_migration_run_signal(
            factory,
            handler,
            now=dt.datetime(2026, 8, 11, 7, tzinfo=dt.timezone.utc),
        )

    assert order == ["executed", "attempt-finished", "signal-acked"]
    release.assert_not_awaited()


@pytest.mark.asyncio
async def test_attempt_bound_handler_abandons_sanitized_failure() -> None:
    """Worker details cannot escape, while an exact failed owner is abandoned."""

    secret = "postgresql://owner:secret@target/private"
    run_uuid = uuid.uuid4()
    signal_claim = MigrationRunSignalClaim(run_uuid, uuid.uuid4())
    attempt_claim = _attempt_claim(run_uuid)
    factory = _transactional_session_factory()

    with patch(
        "app.jobs.migration_run_consumer.acquire_migration_run_attempt",
        new=AsyncMock(return_value=attempt_claim),
    ), patch(
        "app.jobs.migration_run_consumer.finish_migration_run_attempt",
        new=AsyncMock(return_value=True),
    ) as finish:
        handler = make_attempt_bound_migration_run_handler(
            AsyncMock(side_effect=RuntimeError(secret)),
            worker_identity="forward-worker-1",
            attempt_lease_seconds=60,
        )
        with pytest.raises(MigrationRunAttemptHandlerError) as caught:
            await handler(factory, signal_claim)

    assert str(caught.value) == "migration run attempt handler failed"
    assert secret not in repr(caught.value)
    finish.assert_awaited_once_with(
        factory.sessions[1],
        claim=attempt_claim,
        worker_identity="forward-worker-1",
        signal_lease_token=signal_claim.lease_token,
        succeeded=False,
    )


@pytest.mark.asyncio
async def test_attempt_bound_handler_renews_and_cancels_on_ownership_loss() -> None:
    """Losing the DB lease cancels execution and cannot finish as success."""

    run_uuid = uuid.uuid4()
    signal_claim = MigrationRunSignalClaim(run_uuid, uuid.uuid4())
    attempt_claim = _attempt_claim(run_uuid)
    factory = _transactional_session_factory()
    cancelled = asyncio.Event()

    async def executor(*_args: object) -> None:
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    with patch(
        "app.jobs.migration_run_consumer.acquire_migration_run_attempt",
        new=AsyncMock(return_value=attempt_claim),
    ), patch(
        "app.jobs.migration_run_consumer.renew_migration_run_attempt",
        new=AsyncMock(side_effect=[True, False]),
    ) as renew, patch(
        "app.jobs.migration_run_consumer.finish_migration_run_attempt",
        new=AsyncMock(return_value=True),
    ) as finish:
        handler = make_attempt_bound_migration_run_handler(
            executor,
            worker_identity="forward-worker-1",
            attempt_lease_seconds=2,
            heartbeat_interval_s=0.01,
        )
        with pytest.raises(MigrationRunAttemptLeaseLost, match="renewal"):
            await handler(factory, signal_claim)

    assert cancelled.is_set()
    assert renew.await_count == 2
    for index, renewed_call in enumerate(renew.await_args_list, start=1):
        assert renewed_call == call(
            factory.sessions[index],
            claim=attempt_claim,
            worker_identity="forward-worker-1",
            signal_lease_token=signal_claim.lease_token,
            lease_seconds=2,
        )
    finish.assert_awaited_once_with(
        factory.sessions[3],
        claim=attempt_claim,
        worker_identity="forward-worker-1",
        signal_lease_token=signal_claim.lease_token,
        succeeded=False,
    )


@pytest.mark.asyncio
async def test_attempt_bound_handler_fails_closed_when_completion_owner_is_lost() -> None:
    """A successful callback cannot authorize signal ack after DB lease loss."""

    run_uuid = uuid.uuid4()
    signal_claim = MigrationRunSignalClaim(run_uuid, uuid.uuid4())
    attempt_claim = _attempt_claim(run_uuid)
    factory = _transactional_session_factory()
    with patch(
        "app.jobs.migration_run_consumer.acquire_migration_run_attempt",
        new=AsyncMock(return_value=attempt_claim),
    ), patch(
        "app.jobs.migration_run_consumer.finish_migration_run_attempt",
        new=AsyncMock(return_value=False),
    ):
        handler = make_attempt_bound_migration_run_handler(
            AsyncMock(),
            worker_identity="forward-worker-1",
            attempt_lease_seconds=60,
        )
        with pytest.raises(MigrationRunAttemptLeaseLost, match="completion"):
            await handler(factory, signal_claim)


@pytest.mark.asyncio
async def test_attempt_bound_handler_abandons_when_lifecycle_is_cancelled() -> None:
    """Outer signal-lease cancellation removes the durable attempt owner too."""

    run_uuid = uuid.uuid4()
    signal_claim = MigrationRunSignalClaim(run_uuid, uuid.uuid4())
    attempt_claim = _attempt_claim(run_uuid)
    factory = _transactional_session_factory()
    started = asyncio.Event()

    async def executor(*_args: object) -> None:
        started.set()
        await asyncio.Event().wait()

    with patch(
        "app.jobs.migration_run_consumer.acquire_migration_run_attempt",
        new=AsyncMock(return_value=attempt_claim),
    ), patch(
        "app.jobs.migration_run_consumer.finish_migration_run_attempt",
        new=AsyncMock(return_value=True),
    ) as finish:
        handler = make_attempt_bound_migration_run_handler(
            executor,
            worker_identity="forward-worker-1",
            attempt_lease_seconds=60,
        )
        task: asyncio.Future[None] = asyncio.ensure_future(
            handler(factory, signal_claim)
        )
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    finish.assert_awaited_once_with(
        factory.sessions[1],
        claim=attempt_claim,
        worker_identity="forward-worker-1",
        signal_lease_token=signal_claim.lease_token,
        succeeded=False,
    )


@pytest.mark.asyncio
async def test_attempt_abandonment_failure_logs_only_fixed_code(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Cleanup driver details cannot escape when durable renewal is lost."""

    secret = "postgresql://owner:secret@metadata/private"
    run_uuid = uuid.uuid4()
    signal_claim = MigrationRunSignalClaim(run_uuid, uuid.uuid4())
    attempt_claim = _attempt_claim(run_uuid)
    factory = _transactional_session_factory()

    async def executor(*_args: object) -> None:
        await asyncio.Event().wait()

    with patch(
        "app.jobs.migration_run_consumer.acquire_migration_run_attempt",
        new=AsyncMock(return_value=attempt_claim),
    ), patch(
        "app.jobs.migration_run_consumer.renew_migration_run_attempt",
        new=AsyncMock(return_value=False),
    ), patch(
        "app.jobs.migration_run_consumer.finish_migration_run_attempt",
        new=AsyncMock(side_effect=RuntimeError(secret)),
    ):
        handler = make_attempt_bound_migration_run_handler(
            executor,
            worker_identity="forward-worker-1",
            attempt_lease_seconds=2,
            heartbeat_interval_s=0.01,
        )
        with pytest.raises(MigrationRunAttemptLeaseLost, match="renewal"):
            await handler(factory, signal_claim)

    assert "migration_run_attempt_abandon_failed" in caplog.text
    assert secret not in caplog.text


@pytest.mark.asyncio
async def test_attempt_bound_handler_rejects_invalid_timing_before_database_io() -> None:
    """Attempt ownership cannot be configured with unsafe lease timing."""

    factory = _transactional_session_factory()
    signal_claim = MigrationRunSignalClaim(uuid.uuid4(), uuid.uuid4())
    for lease in (True, 0, 301, 1.5):
        with pytest.raises(ValueError, match="attempt lease"):
            make_attempt_bound_migration_run_handler(
                AsyncMock(),
                worker_identity="forward-worker-1",
                attempt_lease_seconds=lease,  # type: ignore[arg-type]
            )
    for heartbeat in (0, float("nan"), 60):
        with pytest.raises(ValueError, match="attempt heartbeat"):
            make_attempt_bound_migration_run_handler(
                AsyncMock(),
                worker_identity="forward-worker-1",
                attempt_lease_seconds=60,
                heartbeat_interval_s=heartbeat,
            )

    assert factory.call_count == 0
    assert signal_claim.migration_run_uuid


@pytest.mark.asyncio
async def test_consumer_acknowledges_exact_lease_only_after_handler_success() -> None:
    """Successful injected work precedes exact-lease acknowledgement."""

    run_uuid = uuid.uuid4()
    claim = MigrationRunSignalClaim(run_uuid, uuid.uuid4())
    order: list[str] = []

    async def handler(
        factory: Callable[[], AsyncSession], actual_claim: MigrationRunSignalClaim
    ) -> None:
        assert factory is _session_factory
        assert actual_claim == claim
        order.append("handled")

    async def ack(actual: MigrationRunSignalClaim) -> bool:
        assert actual == claim
        order.append("acked")
        return True

    with patch(
        "app.jobs.migration_run_consumer.claim_due_migration_run_signal",
        new=AsyncMock(return_value=claim),
    ), patch(
        "app.jobs.migration_run_consumer.ack_migration_run_signal",
        new=ack,
    ), patch(
        "app.jobs.migration_run_consumer.release_migration_run_signal",
        new=AsyncMock(),
    ) as release:
        assert await process_one_migration_run_signal(
            _session_factory,
            handler,
            now=dt.datetime(2026, 8, 11, 7, tzinfo=dt.timezone.utc),
        )

    assert order == ["handled", "acked"]
    release.assert_not_awaited()


@pytest.mark.asyncio
async def test_consumer_releases_exact_lease_after_sanitized_handler_failure() -> None:
    """Failed work is retried without exposing the handler exception or payload."""

    now = dt.datetime(2026, 8, 11, 7, tzinfo=dt.timezone.utc)
    claim = MigrationRunSignalClaim(uuid.uuid4(), uuid.uuid4())
    handler = AsyncMock(
        side_effect=RuntimeError("postgresql://admin:secret@target/private")
    )
    release = AsyncMock(return_value=True)

    with patch(
        "app.jobs.migration_run_consumer.claim_due_migration_run_signal",
        new=AsyncMock(return_value=claim),
    ), patch(
        "app.jobs.migration_run_consumer.ack_migration_run_signal",
        new=AsyncMock(),
    ) as ack, patch(
        "app.jobs.migration_run_consumer.release_migration_run_signal",
        new=release,
    ):
        with pytest.raises(MigrationRunConsumerError) as caught:
            await process_one_migration_run_signal(
                _session_factory,
                handler,
                now=now,
                retry_delay_s=2.5,
            )

    assert str(caught.value) == "migration run handler failed"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    release.assert_awaited_once_with(claim, now + dt.timedelta(seconds=2.5))
    ack.assert_not_awaited()


@pytest.mark.asyncio
async def test_consumer_fails_closed_when_exact_lease_cannot_be_completed() -> None:
    """Lost acknowledgement or release ownership is never reported as success."""

    claim = MigrationRunSignalClaim(uuid.uuid4(), uuid.uuid4())
    now = dt.datetime(2026, 8, 11, 7, tzinfo=dt.timezone.utc)
    with patch(
        "app.jobs.migration_run_consumer.claim_due_migration_run_signal",
        new=AsyncMock(return_value=claim),
    ), patch(
        "app.jobs.migration_run_consumer.ack_migration_run_signal",
        new=AsyncMock(return_value=False),
    ), patch(
        "app.jobs.migration_run_consumer.release_migration_run_signal",
        new=AsyncMock(),
    ):
        with pytest.raises(MigrationRunSignalLeaseLost, match="acknowledgement"):
            await process_one_migration_run_signal(
                _session_factory,
                AsyncMock(),
                now=now,
            )

    with patch(
        "app.jobs.migration_run_consumer.claim_due_migration_run_signal",
        new=AsyncMock(return_value=claim),
    ), patch(
        "app.jobs.migration_run_consumer.ack_migration_run_signal",
        new=AsyncMock(),
    ), patch(
        "app.jobs.migration_run_consumer.release_migration_run_signal",
        new=AsyncMock(return_value=False),
    ):
        with pytest.raises(MigrationRunSignalLeaseLost, match="retry release"):
            await process_one_migration_run_signal(
                _session_factory,
                AsyncMock(side_effect=RuntimeError("hostile detail")),
                now=now,
            )


@pytest.mark.asyncio
async def test_consumer_renews_exact_lease_while_handler_runs() -> None:
    """Long-running work renews its own claim before acknowledgement."""

    claim = MigrationRunSignalClaim(uuid.uuid4(), uuid.uuid4())
    handler_can_finish = asyncio.Event()

    async def handler(
        _factory: Callable[[], AsyncSession], actual_claim: MigrationRunSignalClaim
    ) -> None:
        assert actual_claim == claim
        await handler_can_finish.wait()

    async def renew(
        actual_claim: MigrationRunSignalClaim, **_kwargs: object
    ) -> bool:
        assert actual_claim == claim
        handler_can_finish.set()
        return True

    with patch(
        "app.jobs.migration_run_consumer.claim_due_migration_run_signal",
        new=AsyncMock(return_value=claim),
    ), patch(
        "app.jobs.migration_run_consumer.renew_migration_run_signal",
        new=AsyncMock(side_effect=renew),
    ) as renewal, patch(
        "app.jobs.migration_run_consumer.ack_migration_run_signal",
        new=AsyncMock(return_value=True),
    ) as ack, patch(
        "app.jobs.migration_run_consumer.release_migration_run_signal",
        new=AsyncMock(),
    ) as release:
        assert await process_one_migration_run_signal(
            _session_factory,
            handler,
            lease_seconds=0.1,
            heartbeat_interval_s=0.01,
        )

    renewal.assert_awaited_once_with(claim, lease_seconds=0.1)
    ack.assert_awaited_once_with(claim)
    release.assert_not_awaited()


@pytest.mark.asyncio
async def test_consumer_cancels_handler_when_exact_renewal_is_lost() -> None:
    """Lease loss removes handler authority and cannot become success or retry."""

    claim = MigrationRunSignalClaim(uuid.uuid4(), uuid.uuid4())
    cancelled = asyncio.Event()

    async def handler(
        _factory: Callable[[], AsyncSession], _claim: MigrationRunSignalClaim
    ) -> None:
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    with patch(
        "app.jobs.migration_run_consumer.claim_due_migration_run_signal",
        new=AsyncMock(return_value=claim),
    ), patch(
        "app.jobs.migration_run_consumer.renew_migration_run_signal",
        new=AsyncMock(return_value=False),
    ), patch(
        "app.jobs.migration_run_consumer.ack_migration_run_signal",
        new=AsyncMock(),
    ) as ack, patch(
        "app.jobs.migration_run_consumer.release_migration_run_signal",
        new=AsyncMock(),
    ) as release:
        with pytest.raises(MigrationRunSignalLeaseLost, match="renewal"):
            await process_one_migration_run_signal(
                _session_factory,
                handler,
                lease_seconds=0.1,
                heartbeat_interval_s=0.01,
            )

    assert cancelled.is_set()
    ack.assert_not_awaited()
    release.assert_not_awaited()


@pytest.mark.asyncio
async def test_consumer_lifecycle_cancellation_retrieves_both_tasks() -> None:
    """Shutdown cancellation cannot leave handler or heartbeat tasks running."""

    claim = MigrationRunSignalClaim(uuid.uuid4(), uuid.uuid4())
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def handler(
        _factory: Callable[[], AsyncSession], _claim: MigrationRunSignalClaim
    ) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    with patch(
        "app.jobs.migration_run_consumer.claim_due_migration_run_signal",
        new=AsyncMock(return_value=claim),
    ), patch(
        "app.jobs.migration_run_consumer.renew_migration_run_signal",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.jobs.migration_run_consumer.ack_migration_run_signal",
        new=AsyncMock(),
    ) as ack, patch(
        "app.jobs.migration_run_consumer.release_migration_run_signal",
        new=AsyncMock(),
    ) as release:
        task = asyncio.create_task(
            process_one_migration_run_signal(
                _session_factory,
                handler,
                lease_seconds=60,
                heartbeat_interval_s=20,
            )
        )
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert cancelled.is_set()
    ack.assert_not_awaited()
    release.assert_not_awaited()


@pytest.mark.asyncio
async def test_consumer_empty_queue_and_invalid_timing_are_io_free() -> None:
    """An empty queue sleeps, while invalid bounds fail before signal I/O."""

    claim = AsyncMock(return_value=None)
    handler = AsyncMock()
    with patch(
        "app.jobs.migration_run_consumer.claim_due_migration_run_signal",
        new=claim,
    ), patch(
        "app.jobs.migration_run_consumer.ack_migration_run_signal",
        new=AsyncMock(),
    ), patch(
        "app.jobs.migration_run_consumer.release_migration_run_signal",
        new=AsyncMock(),
    ):
        assert not await process_one_migration_run_signal(
            _session_factory,
            handler,
            now=dt.datetime(2026, 8, 11, 7, tzinfo=dt.timezone.utc),
        )
        for retry_delay in (0, float("inf"), 3601):
            with pytest.raises(ValueError, match="retry delay"):
                await process_one_migration_run_signal(
                    _session_factory,
                    handler,
                    retry_delay_s=retry_delay,
                )
        for heartbeat_interval in (0, float("inf"), 60):
            with pytest.raises(ValueError, match="heartbeat interval"):
                await process_one_migration_run_signal(
                    _session_factory,
                    handler,
                    lease_seconds=60,
                    heartbeat_interval_s=heartbeat_interval,
                )
        with pytest.raises(ValueError, match="include a timezone"):
            await process_one_migration_run_signal(
                _session_factory,
                handler,
                now=dt.datetime(2026, 8, 11, 7),
            )

    claim.assert_awaited_once()
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_consumer_lifecycle_uses_bounded_sleep_and_fixed_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Lifecycle failures retry at a bounded cadence without secret details."""

    process = AsyncMock(
        side_effect=[
            MigrationRunConsumerError("secret detail"),
            False,
            True,
            asyncio.CancelledError,
        ]
    )
    sleep = AsyncMock()
    handler = AsyncMock()
    with patch(
        "app.jobs.migration_run_consumer.process_one_migration_run_signal",
        new=process,
    ), patch("app.jobs.migration_run_consumer.sleep", new=sleep):
        with pytest.raises(asyncio.CancelledError):
            await run_migration_run_consumer_forever(
                _session_factory,
                handler,
                poll_interval_s=0.25,
                retry_delay_s=2,
            )

    assert sleep.await_args_list == [call(0.25), call(0.25)]
    assert "migration_run_consumer_iteration_failed" in caplog.text
    assert "secret detail" not in caplog.text

    for poll_interval in (0, float("nan"), 61):
        with pytest.raises(ValueError, match="poll interval"):
            await run_migration_run_consumer_forever(
                _session_factory,
                handler,
                poll_interval_s=poll_interval,
            )
