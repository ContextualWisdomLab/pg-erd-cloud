"""Bind durable migration attempts to isolated and read-only capabilities.

Queue signals remain UUID-only. Concrete sandbox lifecycle, target credential
resolution, route isolation, and application startup remain injected deployment
responsibilities; this module owns only deterministic attempt orchestration.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import math
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field, replace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.forward.isolated_dry_run import (
    MAX_LOCK_TIMEOUT_MS,
    MAX_STATEMENT_TIMEOUT_MS as MAX_SANDBOX_STATEMENT_TIMEOUT_MS,
    execute_isolated_dry_run,
)
from app.forward.live_preflight import (
    MAX_STATEMENT_TIMEOUT_MS as MAX_PREFLIGHT_STATEMENT_TIMEOUT_MS,
    execute_bound_live_preflight,
)
from app.forward.migration_run import (
    MigrationRunAttemptClaim,
    MigrationRunTransition,
    complete_isolated_dry_run,
    complete_live_preflight,
    transition_migration_run,
)
from app.jobs.migration_dry_run_worker_contract import (
    IsolatedSandboxExecution,
    IsolatedSandboxFactory,
    IsolatedSandboxRequest,
    LivePreflightExecution,
    LivePreflightFactory,
    LivePreflightRequest,
    MigrationDryRunWorkerError,
    SessionFactory,
    _MigrationDryRunWork,
    _invalid_metadata,
    _make_work,
)
from app.jobs.migration_run_consumer import MigrationRunAttemptHandler
from app.jobs.valkey_queue import MigrationRunSignalClaim
from app.models import (
    DbConnection,
    MigrationPlan,
    MigrationRun,
    MigrationRunAttempt,
    SchemaSnapshot,
)

__all__ = [
    "IsolatedSandboxExecution",
    "IsolatedSandboxRequest",
    "GuardedLivePreflightTarget",
    "LivePreflightExecution",
    "LivePreflightRequest",
    "MigrationDryRunWorkerError",
    "guard_live_preflight_handoff",
    "load_guarded_live_preflight_target",
    "make_durable_dry_run_attempt_handler",
]

MAX_SANDBOX_STAGE_TIMEOUT_SECONDS = 900.0
MAX_PREFLIGHT_STAGE_TIMEOUT_SECONDS = 60.0
_SCHEMA_FILTER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_$]{0,62}")


@dataclass(frozen=True)
class GuardedLivePreflightTarget:
    """Encrypted target material and snapshot scope from one exact guard."""

    dsn_ciphertext: bytes = field(repr=False)
    dsn_nonce: bytes = field(repr=False)
    base_schema_snapshot_uuid: uuid.UUID
    schema_filter: str | None = field(repr=False)


def _validated_live_preflight_time(
    request: LivePreflightRequest,
    now: dt.datetime | None,
    *,
    error_message: str,
) -> dt.datetime:
    """Validate exact handoff metadata before any database I/O."""

    checked_at = now if now is not None else dt.datetime.now(dt.timezone.utc)
    uuids = (
        getattr(request, "migration_run_uuid", None),
        getattr(request, "migration_plan_uuid", None),
        getattr(request, "project_space_uuid", None),
        getattr(request, "db_connection_uuid", None),
        getattr(request, "migration_run_attempt_uuid", None),
    )
    if (
        not isinstance(request, LivePreflightRequest)
        or not isinstance(checked_at, dt.datetime)
        or checked_at.tzinfo is None
        or checked_at.utcoffset() is None
        or not all(isinstance(value, uuid.UUID) for value in uuids)
        or isinstance(request.attempt_number, bool)
        or not isinstance(request.attempt_number, int)
        or request.attempt_number < 1
        or isinstance(request.expected_state_version, bool)
        or not isinstance(request.expected_state_version, int)
        or request.expected_state_version < 1
    ):
        raise MigrationDryRunWorkerError(error_message)
    return checked_at


def _live_preflight_handoff_conditions(
    request: LivePreflightRequest,
    checked_at: dt.datetime,
) -> tuple[ColumnElement[bool], ...]:
    """Return the single canonical exact-attempt live-reader predicate."""

    return (
        MigrationRunAttempt.migration_run_attempt_uuid
        == request.migration_run_attempt_uuid,
        MigrationRunAttempt.migration_run_uuid == request.migration_run_uuid,
        MigrationRunAttempt.attempt_number == request.attempt_number,
        MigrationRunAttempt.status == "active",
        MigrationRunAttempt.lease_expires_at > checked_at,
        MigrationRun.migration_run_uuid == request.migration_run_uuid,
        MigrationRun.migration_plan_uuid == request.migration_plan_uuid,
        MigrationRun.project_space_uuid == request.project_space_uuid,
        MigrationRun.run_kind == "dry_run",
        MigrationRun.state == "live_preflight_running",
        MigrationRun.state_version == request.expected_state_version,
        MigrationRun.cancellation_requested.is_(False),
        MigrationPlan.migration_plan_uuid == request.migration_plan_uuid,
        MigrationPlan.project_space_uuid == request.project_space_uuid,
        MigrationPlan.db_connection_uuid == request.db_connection_uuid,
        MigrationPlan.statement_digest == MigrationRun.plan_digest,
        MigrationPlan.expires_at > checked_at,
    )


async def guard_live_preflight_handoff(
    session: AsyncSession,
    request: LivePreflightRequest,
    *,
    now: dt.datetime | None = None,
) -> None:
    """Fail closed unless one fresh query matches the exact live-reader lease.

    Concrete providers can call this server-owned guard immediately before
    resolving the stored target. It returns no credential or connection and
    does not eliminate the gap between this observation and provider access.
    """

    error_message = "migration live-preflight handoff is invalid"
    checked_at = _validated_live_preflight_time(
        request, now, error_message=error_message
    )
    try:
        matched_attempt_uuid = await session.scalar(
            select(MigrationRunAttempt.migration_run_attempt_uuid)
            .select_from(MigrationRunAttempt)
            .join(
                MigrationRun,
                MigrationRun.migration_run_uuid
                == MigrationRunAttempt.migration_run_uuid,
            )
            .join(
                MigrationPlan,
                MigrationPlan.migration_plan_uuid
                == MigrationRun.migration_plan_uuid,
            )
            .where(*_live_preflight_handoff_conditions(request, checked_at))
        )
    except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
        raise
    except Exception:  # noqa: BLE001
        raise MigrationDryRunWorkerError(error_message) from None
    if matched_attempt_uuid != request.migration_run_attempt_uuid:
        raise MigrationDryRunWorkerError(error_message)


async def load_guarded_live_preflight_target(
    session: AsyncSession,
    request: LivePreflightRequest,
    *,
    now: dt.datetime | None = None,
) -> GuardedLivePreflightTarget:
    """Release encrypted target material for one exact active live attempt.

    This performs one metadata statement and deliberately does not decrypt the
    DSN, open a target connection, or grant SQL execution authority.
    """

    error_message = "migration live-preflight target is invalid"
    checked_at = _validated_live_preflight_time(
        request, now, error_message=error_message
    )
    try:
        result = await session.execute(
            select(
                DbConnection.dsn_ciphertext,
                DbConnection.dsn_nonce,
                SchemaSnapshot.schema_snapshot_uuid,
                SchemaSnapshot.schema_filter,
            )
            .select_from(MigrationRunAttempt)
            .join(
                MigrationRun,
                MigrationRun.migration_run_uuid
                == MigrationRunAttempt.migration_run_uuid,
            )
            .join(
                MigrationPlan,
                MigrationPlan.migration_plan_uuid
                == MigrationRun.migration_plan_uuid,
            )
            .join(
                DbConnection,
                DbConnection.db_connection_uuid
                == MigrationPlan.db_connection_uuid,
            )
            .join(
                SchemaSnapshot,
                SchemaSnapshot.schema_snapshot_uuid
                == MigrationPlan.base_schema_snapshot_uuid,
            )
            .where(
                *_live_preflight_handoff_conditions(request, checked_at),
                DbConnection.db_connection_uuid == request.db_connection_uuid,
                DbConnection.project_space_uuid == request.project_space_uuid,
                SchemaSnapshot.project_space_uuid
                == request.project_space_uuid,
                SchemaSnapshot.db_connection_uuid
                == request.db_connection_uuid,
                SchemaSnapshot.status == "succeeded",
                SchemaSnapshot.finished_at.is_not(None),
            )
        )
        row = result.one_or_none()
    except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
        raise
    except Exception:  # noqa: BLE001
        raise MigrationDryRunWorkerError(error_message) from None
    if row is None:
        raise MigrationDryRunWorkerError(error_message)
    ciphertext, nonce, snapshot_uuid, schema_filter = row
    if (
        not isinstance(ciphertext, bytes)
        or not ciphertext
        or not isinstance(nonce, bytes)
        or len(nonce) != 12
        or not isinstance(snapshot_uuid, uuid.UUID)
        or (
            schema_filter is not None
            and (
                not isinstance(schema_filter, str)
                or _SCHEMA_FILTER_RE.fullmatch(schema_filter) is None
            )
        )
    ):
        raise MigrationDryRunWorkerError(error_message)
    return GuardedLivePreflightTarget(
        bytes(ciphertext),
        bytes(nonce),
        snapshot_uuid,
        schema_filter,
    )


async def _load_and_begin(
    session_factory: SessionFactory,
    attempt_claim: MigrationRunAttemptClaim,
) -> _MigrationDryRunWork:
    """Load exact metadata and durably enter the isolated stage when queued."""

    transition_time = dt.datetime.now(dt.timezone.utc)
    try:
        async with session_factory() as session:
            async with session.begin():
                run = await session.scalar(
                    select(MigrationRun)
                    .where(
                        MigrationRun.migration_run_uuid
                        == attempt_claim.migration_run_uuid
                    )
                    .with_for_update()
                )
                if run is None:
                    raise _invalid_metadata()
                plan = await session.scalar(
                    select(MigrationPlan).where(
                        MigrationPlan.migration_plan_uuid
                        == run.migration_plan_uuid
                    )
                )
                if plan is None:
                    raise _invalid_metadata()
                work = _make_work(
                    run, plan, attempt_claim, now=transition_time
                )
                if work.state == "queued":
                    transition = await transition_migration_run(
                        session,
                        migration_run_uuid=work.migration_run_uuid,
                        expected_state_version=work.state_version,
                        next_state="sandbox_running",
                        event_type="sandbox_started",
                        evidence={
                            "attempt_number": work.attempt_number,
                            "migration_run_attempt_uuid": str(
                                work.migration_run_attempt_uuid
                            ),
                        },
                        actor_user_uuid=None,
                        now=transition_time,
                    )
                    if transition.state != "sandbox_running":
                        raise _invalid_metadata()
                    work = replace(
                        work,
                        state=transition.state,
                        state_version=transition.state_version,
                    )
                return work
    except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
        raise
    except MigrationDryRunWorkerError:
        raise
    except Exception:  # noqa: BLE001
        raise MigrationDryRunWorkerError(
            "migration dry-run metadata load failed"
        ) from None


async def _refresh_live_stage(
    session_factory: SessionFactory,
    attempt_claim: MigrationRunAttemptClaim,
    work: _MigrationDryRunWork,
) -> _MigrationDryRunWork:
    """Recheck cancellation, plan integrity, and state immediately before target I/O."""

    refresh_time = dt.datetime.now(dt.timezone.utc)
    try:
        async with session_factory() as session:
            async with session.begin():
                run = await session.scalar(
                    select(MigrationRun)
                    .where(
                        MigrationRun.migration_run_uuid
                        == work.migration_run_uuid
                    )
                    .with_for_update()
                )
                if run is None:
                    raise _invalid_metadata()
                plan = await session.scalar(
                    select(MigrationPlan).where(
                        MigrationPlan.migration_plan_uuid
                        == run.migration_plan_uuid
                    )
                )
                if plan is None:
                    raise _invalid_metadata()
                refreshed = _make_work(
                    run,
                    plan,
                    attempt_claim,
                    now=refresh_time,
                    expected_state_version=work.state_version,
                )
                if (
                    refreshed.state != "live_preflight_running"
                    or refreshed.migration_run_uuid != work.migration_run_uuid
                    or refreshed.migration_plan_uuid != work.migration_plan_uuid
                    or refreshed.project_space_uuid != work.project_space_uuid
                    or refreshed.db_connection_uuid != work.db_connection_uuid
                    or refreshed.base_schema_snapshot_uuid
                    != work.base_schema_snapshot_uuid
                    or refreshed.migration_run_attempt_uuid
                    != work.migration_run_attempt_uuid
                    or refreshed.attempt_number != work.attempt_number
                    or refreshed.plan_digest != work.plan_digest
                ):
                    raise _invalid_metadata()
                return refreshed
    except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
        raise
    except MigrationDryRunWorkerError:
        raise
    except Exception:  # noqa: BLE001
        raise MigrationDryRunWorkerError(
            "migration live-preflight metadata refresh failed"
        ) from None


async def _complete_isolated_stage(
    session_factory: SessionFactory,
    work: _MigrationDryRunWork,
    result: Mapping[str, object],
) -> MigrationRunTransition:
    async with session_factory() as session:
        async with session.begin():
            return await complete_isolated_dry_run(
                session,
                migration_run_uuid=work.migration_run_uuid,
                expected_state_version=work.state_version,
                result=result,
                actor_user_uuid=None,
            )


async def _complete_live_stage(
    session_factory: SessionFactory,
    work: _MigrationDryRunWork,
    result: Mapping[str, object],
) -> MigrationRunTransition:
    async with session_factory() as session:
        async with session.begin():
            return await complete_live_preflight(
                session,
                migration_run_uuid=work.migration_run_uuid,
                expected_state_version=work.state_version,
                result=result,
                actor_user_uuid=None,
            )


def _require_timeout(value: int, *, maximum: int, label: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 1 <= value <= maximum
    ):
        raise ValueError(f"{label} is outside the allowed range")


def _require_stage_timeout(
    value: float,
    *,
    maximum: float,
    label: str,
) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0 < value <= maximum
    ):
        raise ValueError(f"{label} is outside the allowed range")


def make_durable_dry_run_attempt_handler(
    sandbox_factory: IsolatedSandboxFactory,
    live_preflight_factory: LivePreflightFactory,
    *,
    lock_timeout_ms: int = 1_000,
    sandbox_statement_timeout_ms: int = 30_000,
    preflight_statement_timeout_ms: int = 5_000,
    sandbox_stage_timeout_seconds: float = 300.0,
    preflight_stage_timeout_seconds: float = 30.0,
) -> MigrationRunAttemptHandler:
    """Compose one attempt-bound dry run without concrete credential authority.

    The returned handler is compatible with
    ``make_attempt_bound_migration_run_handler``. Concrete sandbox lifecycle,
    target credential resolution, route isolation, process-level termination,
    and application startup remain injected deployment responsibilities.
    Stage timeouts request cooperative task cancellation; they cannot forcibly
    terminate a provider that suppresses cancellation inside this process.
    """

    if not callable(sandbox_factory) or not callable(live_preflight_factory):
        raise ValueError("migration dry-run capability factory is invalid")
    _require_timeout(
        lock_timeout_ms,
        maximum=MAX_LOCK_TIMEOUT_MS,
        label="migration dry-run lock timeout",
    )
    _require_timeout(
        sandbox_statement_timeout_ms,
        maximum=MAX_SANDBOX_STATEMENT_TIMEOUT_MS,
        label="migration dry-run statement timeout",
    )
    _require_timeout(
        preflight_statement_timeout_ms,
        maximum=MAX_PREFLIGHT_STATEMENT_TIMEOUT_MS,
        label="migration live-preflight statement timeout",
    )
    _require_stage_timeout(
        sandbox_stage_timeout_seconds,
        maximum=MAX_SANDBOX_STAGE_TIMEOUT_SECONDS,
        label="migration sandbox stage timeout",
    )
    _require_stage_timeout(
        preflight_stage_timeout_seconds,
        maximum=MAX_PREFLIGHT_STAGE_TIMEOUT_SECONDS,
        label="migration preflight stage timeout",
    )

    async def handle_attempt(
        session_factory: SessionFactory,
        signal_claim: MigrationRunSignalClaim,
        attempt_claim: MigrationRunAttemptClaim,
    ) -> None:
        if signal_claim.migration_run_uuid != attempt_claim.migration_run_uuid:
            raise MigrationDryRunWorkerError(
                "migration dry-run claim is invalid"
            )
        work = await _load_and_begin(session_factory, attempt_claim)

        if work.state == "sandbox_running":
            async def execute_sandbox_stage() -> Mapping[str, object]:
                async with sandbox_factory(work.sandbox_request()) as sandbox:
                    if (
                        not isinstance(sandbox, IsolatedSandboxExecution)
                        or not callable(sandbox.capture_snapshot)
                    ):
                        raise MigrationDryRunWorkerError(
                            "isolated dry-run capability is invalid"
                        )
                    return await execute_isolated_dry_run(
                        sandbox.connection,
                        work.plan_json,
                        expected_plan_digest=work.plan_digest,
                        capture_snapshot=sandbox.capture_snapshot,
                        lock_timeout_ms=lock_timeout_ms,
                        statement_timeout_ms=sandbox_statement_timeout_ms,
                    )

            try:
                isolated_result = await asyncio.wait_for(
                    execute_sandbox_stage(),
                    timeout=sandbox_stage_timeout_seconds,
                )
            except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
                raise
            except Exception:  # noqa: BLE001
                raise MigrationDryRunWorkerError(
                    "isolated dry-run stage failed"
                ) from None
            try:
                transition = await _complete_isolated_stage(
                    session_factory, work, isolated_result
                )
            except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
                raise
            except Exception:  # noqa: BLE001
                raise MigrationDryRunWorkerError(
                    "isolated dry-run completion failed"
                ) from None
            if transition.state != "live_preflight_running":
                raise MigrationDryRunWorkerError(
                    "isolated dry-run completion is invalid"
                )
            work = replace(
                work,
                state=transition.state,
                state_version=transition.state_version,
            )

        if work.state != "live_preflight_running":
            raise MigrationDryRunWorkerError(
                "migration dry-run stage is invalid"
            )
        work = await _refresh_live_stage(
            session_factory, attempt_claim, work
        )

        async def execute_live_stage() -> Mapping[str, object]:
            async with live_preflight_factory(
                work.live_preflight_request()
            ) as live_target:
                if not isinstance(
                    live_target, LivePreflightExecution
                ) or not callable(live_target.capture_snapshot):
                    raise MigrationDryRunWorkerError(
                        "live preflight capability is invalid"
                    )
                return await execute_bound_live_preflight(
                    live_target.connection,
                    work.plan_json,
                    capture_snapshot=live_target.capture_snapshot,
                    statement_timeout_ms=preflight_statement_timeout_ms,
                )

        try:
            preflight_result = await asyncio.wait_for(
                execute_live_stage(),
                timeout=preflight_stage_timeout_seconds,
            )
        except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
            raise
        except Exception:  # noqa: BLE001
            raise MigrationDryRunWorkerError(
                "live preflight stage failed"
            ) from None
        try:
            terminal = await _complete_live_stage(
                session_factory, work, preflight_result
            )
        except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
            raise
        except Exception:  # noqa: BLE001
            raise MigrationDryRunWorkerError(
                "live preflight completion failed"
            ) from None
        if terminal.state not in {"passed", "drifted", "failed"}:
            raise MigrationDryRunWorkerError(
                "live preflight completion is invalid"
            )

    return handle_attempt
