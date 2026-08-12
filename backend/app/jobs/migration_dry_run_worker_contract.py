"""Least-authority contracts for durable dry-run worker orchestration."""

from __future__ import annotations

import datetime as dt
import json
import uuid
from collections.abc import Callable, Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import TypeAlias, cast

import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession

from app.forward.isolated_dry_run import (
    IsolatedPostgresConnection,
    SnapshotCapture as IsolatedSnapshotCapture,
)
from app.forward.live_preflight import SnapshotCapture as LiveSnapshotCapture
from app.forward.migration_plan import verify_migration_plan_digest
from app.forward.migration_run import MigrationRunAttemptClaim

SessionFactory: TypeAlias = Callable[[], AsyncSession]


class MigrationDryRunWorkerError(RuntimeError):
    """Expose one fixed worker-boundary failure without provider details."""


@dataclass(frozen=True)
class IsolatedSandboxRequest:
    """Non-secret materialization identity for one disposable sandbox lease."""

    migration_run_uuid: uuid.UUID
    migration_plan_uuid: uuid.UUID
    project_space_uuid: uuid.UUID
    base_schema_snapshot_uuid: uuid.UUID
    migration_run_attempt_uuid: uuid.UUID
    postgresql_major: int
    base_digest: str
    attempt_number: int


@dataclass(frozen=True)
class LivePreflightRequest:
    """Stored target identity for one separately constrained read-only lease."""

    migration_run_uuid: uuid.UUID
    migration_plan_uuid: uuid.UUID
    project_space_uuid: uuid.UUID
    db_connection_uuid: uuid.UUID
    migration_run_attempt_uuid: uuid.UUID
    attempt_number: int


@dataclass(frozen=True)
class IsolatedSandboxExecution:
    """Already-provisioned isolated connection plus same-sandbox introspection."""

    connection: IsolatedPostgresConnection
    capture_snapshot: IsolatedSnapshotCapture


@dataclass(frozen=True)
class LivePreflightExecution:
    """Already-authorized read-only target connection plus fresh introspection."""

    connection: asyncpg.Connection
    capture_snapshot: LiveSnapshotCapture


IsolatedSandboxFactory: TypeAlias = Callable[
    [IsolatedSandboxRequest],
    AbstractAsyncContextManager[IsolatedSandboxExecution],
]
LivePreflightFactory: TypeAlias = Callable[
    [LivePreflightRequest],
    AbstractAsyncContextManager[LivePreflightExecution],
]


@dataclass(frozen=True)
class _MigrationDryRunWork:
    migration_run_uuid: uuid.UUID
    migration_plan_uuid: uuid.UUID
    project_space_uuid: uuid.UUID
    db_connection_uuid: uuid.UUID
    base_schema_snapshot_uuid: uuid.UUID
    migration_run_attempt_uuid: uuid.UUID
    attempt_number: int
    state: str
    state_version: int
    postgresql_major: int
    base_digest: str
    target_digest: str
    plan_digest: str
    plan_json: Mapping[str, object]

    def sandbox_request(self) -> IsolatedSandboxRequest:
        """Return the least-authority input needed to lease a sandbox."""

        return IsolatedSandboxRequest(
            migration_run_uuid=self.migration_run_uuid,
            migration_plan_uuid=self.migration_plan_uuid,
            project_space_uuid=self.project_space_uuid,
            base_schema_snapshot_uuid=self.base_schema_snapshot_uuid,
            migration_run_attempt_uuid=self.migration_run_attempt_uuid,
            postgresql_major=self.postgresql_major,
            base_digest=self.base_digest,
            attempt_number=self.attempt_number,
        )

    def live_preflight_request(self) -> LivePreflightRequest:
        """Return the identifier-only input needed to lease a live reader."""

        return LivePreflightRequest(
            migration_run_uuid=self.migration_run_uuid,
            migration_plan_uuid=self.migration_plan_uuid,
            project_space_uuid=self.project_space_uuid,
            db_connection_uuid=self.db_connection_uuid,
            migration_run_attempt_uuid=self.migration_run_attempt_uuid,
            attempt_number=self.attempt_number,
        )


def _invalid_metadata() -> MigrationDryRunWorkerError:
    return MigrationDryRunWorkerError(
        "migration dry-run metadata contract is invalid"
    )


def _copy_plan_json(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise _invalid_metadata()
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        copied = json.loads(encoded)
    except (TypeError, ValueError, OverflowError):
        raise _invalid_metadata() from None
    if not isinstance(copied, dict):
        raise _invalid_metadata()
    return cast(dict[str, object], copied)


def _make_work(
    run: object,
    plan: object,
    attempt_claim: MigrationRunAttemptClaim,
    *,
    now: dt.datetime,
    expected_state_version: int | None = None,
) -> _MigrationDryRunWork:
    """Validate one attempt-bound metadata snapshot before external I/O."""

    if now.tzinfo is None or now.utcoffset() is None:
        raise _invalid_metadata()
    plan_json = _copy_plan_json(getattr(plan, "plan_json", None))
    required_state_version = (
        attempt_claim.acquired_state_version
        if expected_state_version is None
        else expected_state_version
    )
    if (
        isinstance(required_state_version, bool)
        or not isinstance(required_state_version, int)
        or required_state_version < 1
    ):
        raise _invalid_metadata()
    try:
        digest_valid = verify_migration_plan_digest(
            plan_json, getattr(plan, "statement_digest", None)
        )
    except Exception:  # noqa: BLE001
        digest_valid = False
    expires_at = getattr(plan, "expires_at", None)
    postgresql_major = plan_json.get("postgresql_major")
    invalid = (
        not isinstance(
            getattr(attempt_claim, "migration_run_attempt_uuid", None), uuid.UUID
        )
        or not isinstance(
            getattr(attempt_claim, "migration_run_uuid", None), uuid.UUID
        )
        or getattr(run, "migration_run_uuid", None)
        != attempt_claim.migration_run_uuid
        or getattr(run, "run_kind", None) != "dry_run"
        or getattr(run, "state", None)
        not in {"queued", "sandbox_running", "live_preflight_running"}
        or getattr(run, "cancellation_requested", None) is not False
        or isinstance(getattr(run, "state_version", None), bool)
        or not isinstance(getattr(run, "state_version", None), int)
        or getattr(run, "state_version", 0) < 1
        or getattr(run, "state_version", None) != required_state_version
        or isinstance(attempt_claim.attempt_number, bool)
        or not isinstance(attempt_claim.attempt_number, int)
        or attempt_claim.attempt_number < 1
        or not isinstance(getattr(run, "project_space_uuid", None), uuid.UUID)
        or not isinstance(getattr(run, "migration_plan_uuid", None), uuid.UUID)
        or getattr(plan, "migration_plan_uuid", None)
        != getattr(run, "migration_plan_uuid", None)
        or getattr(plan, "project_space_uuid", None)
        != getattr(run, "project_space_uuid", None)
        or not isinstance(getattr(plan, "db_connection_uuid", None), uuid.UUID)
        or not isinstance(
            getattr(plan, "base_schema_snapshot_uuid", None), uuid.UUID
        )
        or getattr(run, "plan_digest", None)
        != getattr(plan, "statement_digest", None)
        or not digest_valid
        or not isinstance(expires_at, dt.datetime)
        or expires_at.tzinfo is None
        or expires_at.utcoffset() is None
        or expires_at <= now
        or isinstance(postgresql_major, bool)
        or not isinstance(postgresql_major, int)
        or not 14 <= postgresql_major <= 18
        or plan_json.get("compiler_version")
        != getattr(plan, "compiler_version", None)
        or plan_json.get("base_digest") != getattr(plan, "base_digest", None)
        or plan_json.get("target_digest") != getattr(plan, "target_digest", None)
        or plan_json.get("plan_digest")
        != getattr(plan, "statement_digest", None)
        or plan_json.get("can_dry_run") is not True
        or plan_json.get("blockers") != []
    )
    if invalid:
        raise _invalid_metadata()
    validated_postgresql_major = cast(int, postgresql_major)
    return _MigrationDryRunWork(
        migration_run_uuid=attempt_claim.migration_run_uuid,
        migration_plan_uuid=getattr(run, "migration_plan_uuid"),
        project_space_uuid=getattr(run, "project_space_uuid"),
        db_connection_uuid=getattr(plan, "db_connection_uuid"),
        base_schema_snapshot_uuid=getattr(plan, "base_schema_snapshot_uuid"),
        migration_run_attempt_uuid=attempt_claim.migration_run_attempt_uuid,
        attempt_number=attempt_claim.attempt_number,
        state=getattr(run, "state"),
        state_version=getattr(run, "state_version"),
        postgresql_major=validated_postgresql_major,
        base_digest=getattr(plan, "base_digest"),
        target_digest=getattr(plan, "target_digest"),
        plan_digest=getattr(plan, "statement_digest"),
        plan_json=plan_json,
    )
