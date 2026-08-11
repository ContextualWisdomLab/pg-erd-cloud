"""Identifier-only migration dispatch relay regressions."""

from __future__ import annotations

import datetime as dt
import uuid
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.forward.migration_run import MigrationDispatchClaim
from app.jobs.migration_dispatch_relay import (
    MigrationDispatchSignalUnavailable,
    publish_one_migration_dispatch,
)


def _claim() -> MigrationDispatchClaim:
    return MigrationDispatchClaim(
        migration_run_dispatch_uuid=uuid.uuid4(),
        migration_run_uuid=uuid.uuid4(),
        dispatch_kind="isolated_dry_run",
        attempt_count=1,
    )


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
