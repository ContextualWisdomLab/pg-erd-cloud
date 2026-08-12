"""Execution-neutral migration-run signal consumer contract tests."""

from __future__ import annotations

import asyncio
import datetime as dt
import uuid
from collections.abc import Callable
from unittest.mock import AsyncMock, call, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.migration_run_consumer import (
    MigrationRunConsumerError,
    MigrationRunSignalLeaseLost,
    process_one_migration_run_signal,
    run_migration_run_consumer_forever,
)
from app.jobs.valkey_queue import MigrationRunSignalClaim


def _session_factory() -> AsyncSession:
    """Stand in for the injected metadata-session factory without opening I/O."""

    raise AssertionError("the execution-neutral consumer must not open a session")


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
