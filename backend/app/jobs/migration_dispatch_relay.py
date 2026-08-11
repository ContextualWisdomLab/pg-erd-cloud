"""Publish identifier-only migration outbox claims without execution authority."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import math
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.forward.migration_run import (
    MigrationDispatchClaim,
    claim_one_migration_dispatch,
    mark_migration_dispatch_published,
)
from app.jobs.valkey_queue import enqueue_migration_run_signal

_logger = logging.getLogger(__name__)


class MigrationDispatchSignalUnavailable(RuntimeError):
    """Raised so the caller-owned transaction rolls an unpublished claim back."""


async def publish_one_migration_dispatch(
    session: AsyncSession,
    *,
    now: dt.datetime | None = None,
) -> MigrationDispatchClaim | None:
    """Publish one due run UUID and acknowledge only its exact outbox claim.

    The caller owns the open transaction and must roll it back when this
    function raises. The Valkey sorted-set member is the run UUID, so retrying
    after an ambiguous acknowledgement is idempotent at the signal layer. This
    function neither loads a plan nor starts a worker or SQL execution.
    """

    claim = await claim_one_migration_dispatch(session, now=now)
    if claim is None:
        return None
    if not await enqueue_migration_run_signal(claim.migration_run_uuid, now):
        raise MigrationDispatchSignalUnavailable(
            "migration dispatch signal unavailable"
        )
    if now is None:
        await mark_migration_dispatch_published(session, claim=claim)
    else:
        await mark_migration_dispatch_published(session, claim=claim, now=now)
    return claim


async def run_migration_dispatch_relay_forever(
    session_factory: Callable[[], AsyncSession],
    *,
    poll_interval_s: float = 1.0,
) -> None:
    """Publish due identifier-only outbox rows until lifecycle cancellation.

    Every claim owns a fresh metadata transaction. A successful context exit
    commits the exact-attempt acknowledgement; any publication or database
    failure exits through rollback before a bounded retry delay. Detailed
    exception text is deliberately excluded from logs because drivers and
    adapters may include connection strings or uncontrolled target metadata.
    """

    if not math.isfinite(poll_interval_s) or not 0 < poll_interval_s <= 60:
        raise ValueError("migration dispatch relay interval must be between 0 and 60")

    while True:
        try:
            async with session_factory() as session:
                async with session.begin():
                    claim = await publish_one_migration_dispatch(session)
        except Exception:  # noqa: BLE001
            _logger.warning("migration_dispatch_relay_iteration_failed")
            await asyncio.sleep(poll_interval_s)
            continue

        if claim is None:
            await asyncio.sleep(poll_interval_s)
