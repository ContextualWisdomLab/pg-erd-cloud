"""Publish identifier-only migration outbox claims without execution authority."""

from __future__ import annotations

import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession

from app.forward.migration_run import (
    MigrationDispatchClaim,
    claim_one_migration_dispatch,
    mark_migration_dispatch_published,
)
from app.jobs.valkey_queue import enqueue_migration_run_signal


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
