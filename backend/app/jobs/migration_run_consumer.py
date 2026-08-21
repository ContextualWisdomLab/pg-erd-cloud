"""Consume UUID-only migration-run signals without execution authority.

The consumer owns only Valkey lease completion and retry cadence. An injected
handler receives the exact signal claim and remains responsible for loading
durable metadata, enforcing optimistic state transitions, and eventually
performing an isolated dry run. Keeping that boundary explicit prevents queue
payloads from becoming plan, credential, or SQL authority.
"""

from __future__ import annotations

import datetime as dt
import logging
import math
from asyncio import FIRST_COMPLETED, create_task, gather, sleep, wait
from collections.abc import Awaitable, Callable
from typing import TypeAlias

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.forward.migration_run import (
    APPLY_RUN_STATES,
    DRY_RUN_STATES,
    MAX_MIGRATION_ATTEMPT_LEASE_SECONDS,
    MigrationRunAttemptClaim,
    MigrationRunContractError,
    acquire_migration_run_attempt,
    finish_migration_run_attempt,
    renew_migration_run_attempt,
    transition_migration_run,
)
from app.jobs.valkey_queue import (
    MigrationRunSignalClaim,
    ack_migration_run_signal,
    claim_due_migration_run_signal,
    release_migration_run_signal,
    renew_migration_run_signal,
)
from app.models import MigrationRun, MigrationRunAttempt
from app.settings import settings

_logger = logging.getLogger(__name__)

_ACTIVE_DRY_RUN_STATES = frozenset(
    {"queued", "sandbox_running", "live_preflight_running"}
)
_ACTIVE_APPLY_RUN_STATES = frozenset(
    {"queued", "applying", "reconciling", "verifying"}
)

MigrationRunHandler: TypeAlias = Callable[
    [Callable[[], AsyncSession], MigrationRunSignalClaim], Awaitable[None]
]
MigrationRunAttemptHandler: TypeAlias = Callable[
    [
        Callable[[], AsyncSession],
        MigrationRunSignalClaim,
        MigrationRunAttemptClaim,
    ],
    Awaitable[None],
]


class MigrationRunConsumerError(RuntimeError):
    """Report a fixed consumer failure without carrying handler details."""


class MigrationRunSignalLeaseLost(MigrationRunConsumerError):
    """Report that exact signal-lease completion no longer belongs to this worker."""


class MigrationRunAttemptLeaseLost(MigrationRunConsumerError):
    """Report that the DB-durable attempt no longer belongs to this worker."""


class MigrationRunAttemptHandlerError(MigrationRunConsumerError):
    """Replace attempt-handler failures with one fixed non-secret error."""


def _validate_interval(value: float, *, label: str, maximum: float) -> None:
    if not math.isfinite(value) or not 0 < value <= maximum:
        raise ValueError(
            f"migration run consumer {label} must be between 0 and {maximum:g}"
        )


async def _acquire_attempt(
    session_factory: Callable[[], AsyncSession],
    signal_claim: MigrationRunSignalClaim,
    *,
    worker_identity: str,
    lease_seconds: int,
) -> MigrationRunAttemptClaim:
    """Commit one exact attempt acquisition in its own metadata transaction."""

    async with session_factory() as session:
        async with session.begin():
            return await acquire_migration_run_attempt(
                session,
                migration_run_uuid=signal_claim.migration_run_uuid,
                worker_identity=worker_identity,
                signal_lease_token=signal_claim.lease_token,
                lease_seconds=lease_seconds,
            )


async def _settle_non_executable_run(
    session_factory: Callable[[], AsyncSession],
    signal_claim: MigrationRunSignalClaim,
) -> bool:
    """Settle cancellation or terminal redelivery without replaying work."""

    async with session_factory() as session:
        async with session.begin():
            run = await session.scalar(
                select(MigrationRun)
                .where(
                    MigrationRun.migration_run_uuid
                    == signal_claim.migration_run_uuid
                )
                .with_for_update()
            )
            if run is None:
                return False
            states = (
                DRY_RUN_STATES
                if run.run_kind == "dry_run"
                else APPLY_RUN_STATES
                if run.run_kind == "apply"
                else frozenset()
            )
            active_states = (
                _ACTIVE_DRY_RUN_STATES
                if run.run_kind == "dry_run"
                else _ACTIVE_APPLY_RUN_STATES
                if run.run_kind == "apply"
                else frozenset()
            )
            is_terminal = run.state in states and run.state not in active_states
            can_acknowledge_cancellation = (
                run.cancellation_requested is True
                and (
                    run.run_kind == "dry_run"
                    or (run.run_kind == "apply" and run.state == "queued")
                )
            )
            if not is_terminal and not can_acknowledge_cancellation:
                return False
            active_attempt = await session.scalar(
                select(MigrationRunAttempt)
                .where(
                    MigrationRunAttempt.migration_run_uuid
                    == run.migration_run_uuid,
                    MigrationRunAttempt.status == "active",
                )
                .with_for_update()
                .limit(1)
            )
            if active_attempt is not None:
                abandoned_at = dt.datetime.now(dt.timezone.utc)
                active_attempt.status = "abandoned"
                active_attempt.finished_at = max(
                    abandoned_at, active_attempt.last_heartbeat_at
                )
            if is_terminal:
                return True
            await transition_migration_run(
                session,
                migration_run_uuid=run.migration_run_uuid,
                expected_state_version=run.state_version,
                next_state="cancelled",
                event_type="cancellation_acknowledged",
                evidence={},
                actor_user_uuid=None,
            )
            return True


async def _finish_attempt(
    session_factory: Callable[[], AsyncSession],
    signal_claim: MigrationRunSignalClaim,
    attempt_claim: MigrationRunAttemptClaim,
    *,
    worker_identity: str,
    succeeded: bool,
) -> bool:
    """Commit one exact completion without retaining handler-owned details."""

    async with session_factory() as session:
        async with session.begin():
            return await finish_migration_run_attempt(
                session,
                claim=attempt_claim,
                worker_identity=worker_identity,
                signal_lease_token=signal_claim.lease_token,
                succeeded=succeeded,
            )


async def _attempt_handler_succeeded_without_retaining_error(
    handler: MigrationRunAttemptHandler,
    session_factory: Callable[[], AsyncSession],
    signal_claim: MigrationRunSignalClaim,
    attempt_claim: MigrationRunAttemptClaim,
) -> bool:
    """Discard execution errors before constructing the fixed lifecycle error."""

    try:
        await handler(session_factory, signal_claim, attempt_claim)
    except Exception:  # noqa: BLE001
        return False
    return True


async def _renew_attempt_until_cancelled(
    session_factory: Callable[[], AsyncSession],
    signal_claim: MigrationRunSignalClaim,
    attempt_claim: MigrationRunAttemptClaim,
    *,
    worker_identity: str,
    heartbeat_interval_s: float,
    lease_seconds: int,
) -> None:
    """Renew the exact durable owner using fresh committed transactions."""

    while True:
        await sleep(heartbeat_interval_s)
        async with session_factory() as session:
            async with session.begin():
                renewed = await renew_migration_run_attempt(
                    session,
                    claim=attempt_claim,
                    worker_identity=worker_identity,
                    signal_lease_token=signal_claim.lease_token,
                    lease_seconds=lease_seconds,
                )
        if not renewed:
            return


async def _run_attempt_handler_under_exact_lease(
    handler: MigrationRunAttemptHandler,
    session_factory: Callable[[], AsyncSession],
    signal_claim: MigrationRunSignalClaim,
    attempt_claim: MigrationRunAttemptClaim,
    *,
    worker_identity: str,
    heartbeat_interval_s: float,
    lease_seconds: int,
) -> bool:
    """Cancel attempt execution as soon as durable ownership is lost."""

    handler_task = create_task(
        _attempt_handler_succeeded_without_retaining_error(
            handler, session_factory, signal_claim, attempt_claim
        )
    )
    heartbeat_task = create_task(
        _renew_attempt_until_cancelled(
            session_factory,
            signal_claim,
            attempt_claim,
            worker_identity=worker_identity,
            heartbeat_interval_s=heartbeat_interval_s,
            lease_seconds=lease_seconds,
        )
    )
    try:
        done, _ = await wait(
            {handler_task, heartbeat_task},
            return_when=FIRST_COMPLETED,
        )
        if handler_task not in done:
            handler_task.cancel()
            await gather(handler_task, return_exceptions=True)
            await gather(heartbeat_task, return_exceptions=True)
            raise MigrationRunAttemptLeaseLost(
                "migration run attempt renewal ended without handler completion"
            ) from None
        heartbeat_task.cancel()
        await gather(heartbeat_task, return_exceptions=True)
        return handler_task.result()
    finally:
        for task in (handler_task, heartbeat_task):
            if not task.done():
                task.cancel()
        await gather(handler_task, heartbeat_task, return_exceptions=True)


def make_attempt_bound_migration_run_handler(
    handler: MigrationRunAttemptHandler,
    *,
    worker_identity: str,
    attempt_lease_seconds: int = 60,
    heartbeat_interval_s: float | None = None,
) -> MigrationRunHandler:
    """Bind one injected executor to both signal and durable attempt ownership.

    The returned handler remains execution-neutral: it accepts no connection,
    credential, plan, statement, or target data. It commits acquisition before
    calling the injected executor, renews with fresh transactions, and records
    exact-owner completion before the outer consumer may acknowledge Valkey.
    """

    if (
        isinstance(attempt_lease_seconds, bool)
        or not isinstance(attempt_lease_seconds, int)
        or not 1
        <= attempt_lease_seconds
        <= MAX_MIGRATION_ATTEMPT_LEASE_SECONDS
    ):
        raise ValueError(
            "migration run consumer attempt lease must be between 1 and "
            f"{MAX_MIGRATION_ATTEMPT_LEASE_SECONDS}"
        )
    heartbeat = (
        attempt_lease_seconds / 3
        if heartbeat_interval_s is None
        else heartbeat_interval_s
    )
    _validate_interval(
        heartbeat,
        label="attempt heartbeat interval",
        maximum=attempt_lease_seconds,
    )
    if heartbeat >= attempt_lease_seconds:
        raise ValueError(
            "migration run consumer attempt heartbeat interval must be shorter "
            "than lease"
        )

    async def attempt_bound_handler(
        session_factory: Callable[[], AsyncSession],
        signal_claim: MigrationRunSignalClaim,
    ) -> None:
        try:
            attempt_claim = await _acquire_attempt(
                session_factory,
                signal_claim,
                worker_identity=worker_identity,
                lease_seconds=attempt_lease_seconds,
            )
        except MigrationRunContractError:
            if await _settle_non_executable_run(
                session_factory, signal_claim
            ):
                return
            raise
        try:
            succeeded = await _run_attempt_handler_under_exact_lease(
                handler,
                session_factory,
                signal_claim,
                attempt_claim,
                worker_identity=worker_identity,
                heartbeat_interval_s=heartbeat,
                lease_seconds=attempt_lease_seconds,
            )
        except BaseException:
            try:
                await _finish_attempt(
                    session_factory,
                    signal_claim,
                    attempt_claim,
                    worker_identity=worker_identity,
                    succeeded=False,
                )
            except Exception:  # noqa: BLE001
                _logger.warning("migration_run_attempt_abandon_failed")
            raise

        if not await _finish_attempt(
            session_factory,
            signal_claim,
            attempt_claim,
            worker_identity=worker_identity,
            succeeded=succeeded,
        ):
            raise MigrationRunAttemptLeaseLost(
                "migration run attempt completion lost its exact lease"
            )
        if not succeeded:
            raise MigrationRunAttemptHandlerError(
                "migration run attempt handler failed"
            )

    return attempt_bound_handler


async def _handler_succeeded_without_retaining_error(
    handler: MigrationRunHandler,
    session_factory: Callable[[], AsyncSession],
    claim: MigrationRunSignalClaim,
) -> bool:
    """Discard handler exceptions before the fixed public error is created."""

    try:
        await handler(session_factory, claim)
    except Exception:  # noqa: BLE001
        return False
    return True


async def _renew_claim_until_cancelled(
    claim: MigrationRunSignalClaim,
    *,
    heartbeat_interval_s: float,
    lease_seconds: float,
) -> None:
    """Keep one exact claim live until cancelled or ownership is lost."""

    while True:
        await sleep(heartbeat_interval_s)
        if not await renew_migration_run_signal(
            claim, lease_seconds=lease_seconds
        ):
            return


async def _run_handler_under_exact_lease(
    handler: MigrationRunHandler,
    session_factory: Callable[[], AsyncSession],
    claim: MigrationRunSignalClaim,
    *,
    heartbeat_interval_s: float,
    lease_seconds: float,
) -> bool:
    """Cancel handler authority immediately when exact renewal is lost."""

    handler_task = create_task(
        _handler_succeeded_without_retaining_error(handler, session_factory, claim)
    )
    heartbeat_task = create_task(
        _renew_claim_until_cancelled(
            claim,
            heartbeat_interval_s=heartbeat_interval_s,
            lease_seconds=lease_seconds,
        )
    )
    try:
        done, _ = await wait(
            {handler_task, heartbeat_task},
            return_when=FIRST_COMPLETED,
        )
        if handler_task not in done:
            handler_task.cancel()
            await gather(handler_task, return_exceptions=True)
            await gather(heartbeat_task, return_exceptions=True)
            raise MigrationRunSignalLeaseLost(
                "migration run renewal ended without handler completion"
            ) from None
        heartbeat_task.cancel()
        await gather(heartbeat_task, return_exceptions=True)
        return handler_task.result()
    finally:
        for task in (handler_task, heartbeat_task):
            if not task.done():
                task.cancel()
        await gather(handler_task, heartbeat_task, return_exceptions=True)


async def process_one_migration_run_signal(
    session_factory: Callable[[], AsyncSession],
    handler: MigrationRunHandler,
    *,
    now: dt.datetime | None = None,
    retry_delay_s: float = 5.0,
    lease_seconds: float | None = None,
    heartbeat_interval_s: float | None = None,
) -> bool:
    """Process one exact signal lease and return whether work was claimed.

    The handler receives the exact claim rather than an unbound UUID. A
    successful handler must win exact-lease acknowledgement. A failed handler
    receives no acknowledgement and the same exact lease is released at a
    bounded future score. Handler exceptions are deliberately replaced with a
    fixed error so DSNs, SQL, credentials, or target data cannot escape through
    lifecycle logs.
    """

    _validate_interval(retry_delay_s, label="retry delay", maximum=3600)
    duration = (
        settings.migration_run_signal_lease_seconds
        if lease_seconds is None
        else lease_seconds
    )
    _validate_interval(duration, label="lease", maximum=3600)
    heartbeat = duration / 3 if heartbeat_interval_s is None else heartbeat_interval_s
    _validate_interval(
        heartbeat,
        label="heartbeat interval",
        maximum=duration,
    )
    if heartbeat >= duration:
        raise ValueError(
            "migration run consumer heartbeat interval must be shorter than lease"
        )
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("migration run consumer time must include a timezone")

    claim = await claim_due_migration_run_signal(
        now=current, lease_seconds=duration
    )
    if claim is None:
        return False

    if not await _run_handler_under_exact_lease(
        handler,
        session_factory,
        claim,
        heartbeat_interval_s=heartbeat,
        lease_seconds=duration,
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
