"""Identifier-only migration dispatch relay regressions."""

from __future__ import annotations

import asyncio
import datetime as dt
import uuid
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.forward.migration_run import MigrationDispatchClaim
from app.jobs.migration_dispatch_relay import (
    MigrationDispatchSignalUnavailable,
    publish_one_migration_dispatch,
    run_migration_dispatch_relay_forever,
)


def _claim() -> MigrationDispatchClaim:
    return MigrationDispatchClaim(
        migration_run_dispatch_uuid=uuid.uuid4(),
        migration_run_uuid=uuid.uuid4(),
        dispatch_kind="isolated_dry_run",
        attempt_count=1,
    )


def _session_factory() -> MagicMock:
    """Return one async session and transaction context for relay-loop tests."""

    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=None)
    transaction.__aexit__ = AsyncMock(return_value=False)
    session.begin.return_value = transaction
    factory = MagicMock(return_value=session)
    factory.session = session
    factory.transaction = transaction
    return factory


@pytest.mark.asyncio
async def test_empty_outbox_does_not_touch_queue_or_transaction() -> None:
    """An empty due outbox is a bounded no-op."""

    session_double = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    session = cast(AsyncSession, session_double)
    with patch(
        "app.jobs.migration_dispatch_relay.claim_one_migration_dispatch",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.jobs.migration_dispatch_relay.enqueue_migration_run_signal",
        new=AsyncMock(),
    ) as enqueue:
        assert await publish_one_migration_dispatch(session) is None

    enqueue.assert_not_awaited()
    session_double.commit.assert_not_awaited()
    session_double.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_relay_publishes_only_run_identity_then_marks_exact_claim() -> None:
    """The queue signal precedes acknowledgement in the caller transaction."""

    claim = _claim()
    session_double = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    session = cast(AsyncSession, session_double)
    with patch(
        "app.jobs.migration_dispatch_relay.claim_one_migration_dispatch",
        new=AsyncMock(return_value=claim),
    ), patch(
        "app.jobs.migration_dispatch_relay.enqueue_migration_run_signal",
        new=AsyncMock(return_value=True),
    ) as enqueue, patch(
        "app.jobs.migration_dispatch_relay.mark_migration_dispatch_published",
        new=AsyncMock(),
    ) as mark:
        published = await publish_one_migration_dispatch(session)

    assert published == claim
    enqueue.assert_awaited_once()
    assert enqueue.await_args is not None
    assert enqueue.await_args.args == (claim.migration_run_uuid, None)
    mark.assert_awaited_once_with(session, claim=claim)
    session_double.commit.assert_not_awaited()
    session_double.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_relay_uses_one_explicit_clock_for_claim_and_acknowledgement() -> None:
    """One caller clock binds due selection to exact-attempt acknowledgement."""

    claim = _claim()
    now = dt.datetime(2026, 8, 11, 7, tzinfo=dt.timezone.utc)
    session_double = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    session = cast(AsyncSession, session_double)
    with patch(
        "app.jobs.migration_dispatch_relay.claim_one_migration_dispatch",
        new=AsyncMock(return_value=claim),
    ) as claim_one, patch(
        "app.jobs.migration_dispatch_relay.enqueue_migration_run_signal",
        new=AsyncMock(return_value=True),
    ) as enqueue, patch(
        "app.jobs.migration_dispatch_relay.mark_migration_dispatch_published",
        new=AsyncMock(),
    ) as mark:
        assert await publish_one_migration_dispatch(session, now=now) == claim

    claim_one.assert_awaited_once_with(session, now=now)
    enqueue.assert_awaited_once_with(claim.migration_run_uuid, now)
    mark.assert_awaited_once_with(session, claim=claim, now=now)
    session_double.commit.assert_not_awaited()
    session_double.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_relay_failure_remains_pending_by_requiring_caller_rollback() -> None:
    """Unavailable queue publication cannot acknowledge the outbox row."""

    claim = _claim()
    session_double = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    session = cast(AsyncSession, session_double)
    with patch(
        "app.jobs.migration_dispatch_relay.claim_one_migration_dispatch",
        new=AsyncMock(return_value=claim),
    ), patch(
        "app.jobs.migration_dispatch_relay.enqueue_migration_run_signal",
        new=AsyncMock(return_value=False),
    ), patch(
        "app.jobs.migration_dispatch_relay.mark_migration_dispatch_published",
        new=AsyncMock(),
    ) as mark:
        with pytest.raises(
            MigrationDispatchSignalUnavailable,
            match="signal unavailable",
        ):
            await publish_one_migration_dispatch(session)

    mark.assert_not_awaited()
    session_double.commit.assert_not_awaited()
    session_double.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_scheduled_relay_commits_each_claim_and_polls_after_empty() -> None:
    """The lifecycle drains one transaction at a time and idles when empty."""

    claim = _claim()
    factory = _session_factory()
    with patch(
        "app.jobs.migration_dispatch_relay.publish_one_migration_dispatch",
        new=AsyncMock(side_effect=[claim, None]),
    ) as publish, patch(
        "app.jobs.migration_dispatch_relay.asyncio.sleep",
        new=AsyncMock(side_effect=asyncio.CancelledError),
    ) as sleep:
        with pytest.raises(asyncio.CancelledError):
            await run_migration_dispatch_relay_forever(factory, poll_interval_s=0.25)

    assert publish.await_count == 2
    assert factory.call_count == 2
    assert factory.session.begin.call_count == 2
    assert factory.transaction.__aexit__.await_count == 2
    sleep.assert_awaited_once_with(0.25)


@pytest.mark.asyncio
async def test_scheduled_relay_rolls_back_failed_publish_and_logs_fixed_code(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Publication failure is rolled back without logging exception contents."""

    secret = "postgresql://admin:secret@target.example/customer"
    factory = _session_factory()
    with patch(
        "app.jobs.migration_dispatch_relay.publish_one_migration_dispatch",
        new=AsyncMock(side_effect=[RuntimeError(secret), None]),
    ), patch(
        "app.jobs.migration_dispatch_relay.asyncio.sleep",
        new=AsyncMock(side_effect=[None, asyncio.CancelledError]),
    ):
        with pytest.raises(asyncio.CancelledError):
            await run_migration_dispatch_relay_forever(factory, poll_interval_s=0.5)

    first_exit_args = factory.transaction.__aexit__.await_args_list[0]
    assert first_exit_args.args[0] is RuntimeError
    assert "migration_dispatch_relay_iteration_failed" in caplog.text
    assert secret not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("interval", [0, -1, float("inf")])
async def test_scheduled_relay_rejects_unbounded_poll_interval(interval: float) -> None:
    """A misconfigured lifecycle cannot become a busy loop."""

    with pytest.raises(ValueError, match="interval must be between"):
        await run_migration_dispatch_relay_forever(
            _session_factory(), poll_interval_s=interval
        )
