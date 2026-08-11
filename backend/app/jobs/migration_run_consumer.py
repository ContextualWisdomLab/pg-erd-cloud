"""Consume UUID-only migration-run signals without execution authority.

The consumer owns only Valkey lease completion and retry cadence. An injected
handler remains responsible for loading durable metadata, enforcing optimistic
state transitions, and eventually performing an isolated dry run. Keeping that
boundary explicit prevents queue payloads from becoming plan, credential, or
SQL authority.
"""

from __future__ import annotations

import datetime as dt
import logging
import math
import uuid
from asyncio import sleep
from collections.abc import Awaitable, Callable
from typing import TypeAlias

from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.valkey_queue import (
    ack_migration_run_signal,
    claim_due_migration_run_signal,
    release_migration_run_signal,
)

_logger = logging.getLogger(__name__)

MigrationRunHandler: TypeAlias = Callable[
    [Callable[[], AsyncSession], uuid.UUID], Awaitable[None]
]


class MigrationRunConsumerError(RuntimeError):
    """Report a fixed consumer failure without carrying handler details."""


class MigrationRunSignalLeaseLost(MigrationRunConsumerError):
    """Report that exact signal-lease completion no longer belongs to this worker."""


def _validate_interval(value: float, *, label: str, maximum: float) -> None:
    if not math.isfinite(value) or not 0 < value <= maximum:
        raise ValueError(
            f"migration run consumer {label} must be between 0 and {maximum:g}"
        )


async def _handler_succeeded_without_retaining_error(
    handler: MigrationRunHandler,
    session_factory: Callable[[], AsyncSession],
    migration_run_uuid: uuid.UUID,
) -> bool:
    """Discard handler exceptions before the fixed public error is created."""

    try:
        await handler(session_factory, migration_run_uuid)
    except Exception:  # noqa: BLE001
        return False
    return True


async def process_one_migration_run_signal(
    session_factory: Callable[[], AsyncSession],
    handler: MigrationRunHandler,
    *,
    now: dt.datetime | None = None,
    retry_delay_s: float = 5.0,
) -> bool:
    """Process one exact signal lease and return whether work was claimed.

    A successful handler must win exact-lease acknowledgement. A failed handler
    receives no acknowledgement and the same exact lease is released at a
    bounded future score. Handler exceptions are deliberately replaced with a
    fixed error so DSNs, SQL, credentials, or target data cannot escape through
    lifecycle logs.
    """

    _validate_interval(retry_delay_s, label="retry delay", maximum=3600)
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("migration run consumer time must include a timezone")

    claim = await claim_due_migration_run_signal(now=current)
    if claim is None:
        return False

    if not await _handler_succeeded_without_retaining_error(
        handler, session_factory, claim.migration_run_uuid
    ):
        retry_at = current + dt.timedelta(seconds=retry_delay_s)
        if not await release_migration_run_signal(claim, retry_at):
            raise MigrationRunSignalLeaseLost(
                "migration run retry release lost its exact lease"
            )
        raise MigrationRunConsumerError("migration run handler failed")

    if not await ack_migration_run_signal(claim):
        raise MigrationRunSignalLeaseLost(
            "migration run acknowledgement lost its exact lease"
        )
    return True


async def run_migration_run_consumer_forever(
    session_factory: Callable[[], AsyncSession],
    handler: MigrationRunHandler,
    *,
    poll_interval_s: float = 1.0,
    retry_delay_s: float = 5.0,
) -> None:
    """Run the injected migration handler until lifecycle cancellation.

    This function is intentionally not wired into application startup until a
    compatible isolated-dry-run handler exists. Cancellation is not caught;
    every other iteration failure emits only a stable non-secret code and
    waits before another claim.
    """

    _validate_interval(poll_interval_s, label="poll interval", maximum=60)
    _validate_interval(retry_delay_s, label="retry delay", maximum=3600)
    while True:
        try:
            processed = await process_one_migration_run_signal(
                session_factory,
                handler,
                retry_delay_s=retry_delay_s,
            )
        except Exception:  # noqa: BLE001
            _logger.warning("migration_run_consumer_iteration_failed")
            await sleep(poll_interval_s)
            continue
        if not processed:
            await sleep(poll_interval_s)
