"""Durable migration-run state and evidence contracts.

This module is deliberately independent from queue delivery. It defines the
states that may become durable product evidence, hashes caller idempotency keys,
and prevents raw SQL or credential-bearing fields from entering run events.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.forward.migration_plan import verify_migration_plan_digest
from app.models import MigrationPlan, MigrationRun, MigrationRunEvent

MAX_IDEMPOTENCY_KEY_BYTES = 255
MAX_RUN_EVIDENCE_BYTES = 16_384
MAX_RUN_EVIDENCE_DEPTH = 8
MAX_RUN_EVIDENCE_ITEMS = 256
MAX_RUN_EVIDENCE_STRING_BYTES = 2_048

DRY_RUN_STATES = frozenset(
    {
        "queued",
        "sandbox_running",
        "live_preflight_running",
        "passed",
        "drifted",
        "failed",
    }
)
APPLY_RUN_STATES = frozenset(
    {
        "queued",
        "applying",
        "reconciling",
        "verifying",
        "verified",
        "drifted_no_apply",
        "not_applied",
        "verification_failed",
        "failed_rolled_back",
        "applied_with_drift",
        "outcome_unknown",
    }
)

_TRANSITIONS = {
    "dry_run": {
        "queued": frozenset({"sandbox_running", "failed"}),
        "sandbox_running": frozenset({"live_preflight_running", "failed"}),
        "live_preflight_running": frozenset({"passed", "drifted", "failed"}),
    },
    "apply": {
        "queued": frozenset({"applying", "drifted_no_apply"}),
        "applying": frozenset(
            {"reconciling", "verifying", "failed_rolled_back", "outcome_unknown"}
        ),
        "reconciling": frozenset(
            {"verifying", "verified", "not_applied", "outcome_unknown"}
        ),
        "verifying": frozenset(
            {"verified", "verification_failed", "applied_with_drift"}
        ),
    },
}

_FORBIDDEN_EVIDENCE_TOKENS = frozenset(
    {"credential", "dsn", "password", "secret", "sql", "token"}
)
_POSTGRES_CONNECTION_STRING = re.compile(
    r"postgres(?:ql)?(?:\+[a-z0-9_.-]+)?://", re.IGNORECASE
)
_HEX_DIGEST = re.compile(r"[0-9a-f]{64}")
_EVENT_TYPE = re.compile(r"[a-z][a-z0-9_]{0,63}")


class MigrationRunContractError(ValueError):
    """Raised when run state or durable evidence violates the v1 contract."""


@dataclass(frozen=True)
class MigrationRunTransition:
    """The durable state identity produced by one successful CAS transition."""

    state: str
    state_version: int
    started_at: dt.datetime | None
    finished_at: dt.datetime | None


@dataclass(frozen=True)
class MigrationRunCreation:
    """The durable identity selected by one idempotent creation request."""

    migration_run_uuid: uuid.UUID
    state: str
    state_version: int
    reused: bool


@dataclass(frozen=True)
class MigrationRunCancellation:
    """The durable cancellation-intent identity selected by one CAS request."""

    state: str
    state_version: int
    reused: bool


def validate_run_transition(run_kind: str, current_state: str, next_state: str) -> None:
    """Reject a state transition outside the exact dry-run/apply graph."""

    transitions = _TRANSITIONS.get(run_kind)
    if transitions is None:
        raise MigrationRunContractError(f"unknown run kind {run_kind!r}")
    if next_state not in transitions.get(current_state, frozenset()):
        raise MigrationRunContractError(
            f"invalid transition for {run_kind}: {current_state} -> {next_state}"
        )


def hash_idempotency_key(value: str) -> str:
    """Return a storage-safe digest for one bounded opaque request key."""

    encoded = value.encode("utf-8")
    if not encoded or len(encoded) > MAX_IDEMPOTENCY_KEY_BYTES:
        raise MigrationRunContractError("idempotency key length is invalid")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        raise MigrationRunContractError("idempotency key contains a control character")
    return hashlib.sha256(encoded).hexdigest()


def digest_run_request(
    *,
    project_space_uuid: uuid.UUID,
    migration_plan_uuid: uuid.UUID,
    run_kind: str,
    plan_digest: str,
    requested_by_user_uuid: uuid.UUID,
) -> str:
    """Bind one versioned run intent for idempotency conflict detection."""

    if run_kind not in {"dry_run", "apply"}:
        raise MigrationRunContractError("run kind is invalid")
    if re.fullmatch(r"[0-9a-f]{64}", plan_digest) is None:
        raise MigrationRunContractError("plan digest is invalid")
    request = {
        "contract_version": "migration-run-request/v1",
        "migration_plan_uuid": str(migration_plan_uuid),
        "plan_digest": plan_digest,
        "project_space_uuid": str(project_space_uuid),
        "requested_by_user_uuid": str(requested_by_user_uuid),
        "run_kind": run_kind,
    }
    encoded = json.dumps(
        request, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def digest_run_event(
    *,
    migration_run_uuid: uuid.UUID,
    sequence_number: int,
    event_type: str,
    state_before: str | None,
    state_after: str,
    evidence: Mapping[str, object],
    actor_user_uuid: uuid.UUID | None,
    created_at: dt.datetime,
    previous_event_digest: str | None,
) -> str:
    """Return the versioned digest for one canonical event-chain link."""

    if not isinstance(migration_run_uuid, uuid.UUID):
        raise MigrationRunContractError("migration run UUID is invalid")
    if (
        isinstance(sequence_number, bool)
        or not isinstance(sequence_number, int)
        or sequence_number < 1
    ):
        raise MigrationRunContractError("event sequence is invalid")
    if _EVENT_TYPE.fullmatch(event_type) is None:
        raise MigrationRunContractError("event type is invalid")
    if not isinstance(state_after, str) or not state_after:
        raise MigrationRunContractError("event state is invalid")
    if state_before is not None and (
        not isinstance(state_before, str) or not state_before
    ):
        raise MigrationRunContractError("event state is invalid")
    if actor_user_uuid is not None and not isinstance(actor_user_uuid, uuid.UUID):
        raise MigrationRunContractError("event actor UUID is invalid")
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise MigrationRunContractError("event time must include a timezone")
    if sequence_number == 1:
        if previous_event_digest is not None:
            raise MigrationRunContractError(
                "genesis event must not have a previous digest"
            )
    elif (
        previous_event_digest is None
        or _HEX_DIGEST.fullmatch(previous_event_digest) is None
    ):
        raise MigrationRunContractError("previous event digest is invalid")

    event = {
        "actor_user_uuid": (
            str(actor_user_uuid) if actor_user_uuid is not None else None
        ),
        "contract_version": "migration-run-event/v1",
        "created_at": created_at.astimezone(dt.timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z"),
        "event_type": event_type,
        "evidence": canonicalize_run_evidence(evidence),
        "migration_run_uuid": str(migration_run_uuid),
        "previous_event_digest": previous_event_digest,
        "sequence_number": sequence_number,
        "state_after": state_after,
        "state_before": state_before,
    }
    encoded = json.dumps(
        event,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_evidence(value: object, *, path: str, depth: int) -> Any:
    if depth > MAX_RUN_EVIDENCE_DEPTH:
        raise MigrationRunContractError("run evidence nesting is too deep")
    if value is None or isinstance(value, (bool, int, str)):
        if isinstance(value, str):
            if len(value.encode("utf-8")) > MAX_RUN_EVIDENCE_STRING_BYTES:
                raise MigrationRunContractError("run evidence string is too large")
            if _POSTGRES_CONNECTION_STRING.search(value):
                raise MigrationRunContractError(
                    "run evidence must not contain a PostgreSQL connection string"
                )
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise MigrationRunContractError("run evidence number must be finite")
        return value
    if isinstance(value, Mapping):
        if len(value) > MAX_RUN_EVIDENCE_ITEMS:
            raise MigrationRunContractError("run evidence object has too many fields")
        result: dict[str, Any] = {}
        for key, nested in value.items():
            if not isinstance(key, str):
                raise MigrationRunContractError("run evidence field name must be text")
            separated_key = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
            tokens = {
                token
                for token in re.split(r"[^a-z0-9]+", separated_key.casefold())
                if token
            }
            if tokens & _FORBIDDEN_EVIDENCE_TOKENS:
                raise MigrationRunContractError(
                    f"forbidden evidence field at {path}.{key}"
                )
            result[key] = _validate_evidence(
                nested, path=f"{path}.{key}", depth=depth + 1
            )
        return result
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        if len(value) > MAX_RUN_EVIDENCE_ITEMS:
            raise MigrationRunContractError("run evidence list has too many items")
        return [
            _validate_evidence(item, path=f"{path}[{index}]", depth=depth + 1)
            for index, item in enumerate(value)
        ]
    raise MigrationRunContractError(f"unsupported run evidence value at {path}")


def canonicalize_run_evidence(value: Mapping[str, object]) -> dict[str, Any]:
    """Return bounded canonical JSON evidence without SQL or credential fields."""

    normalized = _validate_evidence(value, path="evidence", depth=0)
    encoded = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if len(encoded) > MAX_RUN_EVIDENCE_BYTES:
        raise MigrationRunContractError("run evidence is too large")
    return cast(dict[str, Any], json.loads(encoded))


async def create_migration_run(
    session: AsyncSession,
    *,
    plan: MigrationPlan,
    run_kind: str,
    idempotency_key: str,
    requested_by_user_uuid: uuid.UUID,
    evidence: Mapping[str, object],
    now: dt.datetime | None = None,
) -> MigrationRunCreation:
    """Select one durable dry-run identity without exposing execution authority.

    The PostgreSQL uniqueness constraint is the concurrency winner. The caller
    owns the transaction and queue publication; this function never commits or
    signals a worker. Apply creation remains fail-closed until approval and
    passed-dry-run bindings are persisted.
    """

    if run_kind == "apply":
        raise MigrationRunContractError("apply run creation is not implemented")
    if run_kind != "dry_run":
        raise MigrationRunContractError("run kind is invalid")
    transition_time = now or dt.datetime.now(dt.timezone.utc)
    if transition_time.tzinfo is None or transition_time.utcoffset() is None:
        raise MigrationRunContractError("creation time must include a timezone")
    key_hash = hash_idempotency_key(idempotency_key)
    canonical_evidence = canonicalize_run_evidence(evidence)
    plan_json = plan.plan_json
    if (
        not verify_migration_plan_digest(plan_json, plan.statement_digest)
        or plan_json.get("compiler_version") != plan.compiler_version
        or plan_json.get("base_digest") != plan.base_digest
        or plan_json.get("target_digest") != plan.target_digest
    ):
        raise MigrationRunContractError("migration plan integrity verification failed")
    if plan.expires_at <= transition_time:
        raise MigrationRunContractError("migration plan expired")
    if plan_json.get("can_dry_run") is not True or plan_json.get("blockers"):
        raise MigrationRunContractError("migration plan cannot be dry-run")

    request_digest = digest_run_request(
        project_space_uuid=plan.project_space_uuid,
        migration_plan_uuid=plan.migration_plan_uuid,
        run_kind=run_kind,
        plan_digest=plan.statement_digest,
        requested_by_user_uuid=requested_by_user_uuid,
    )
    run_uuid = uuid.uuid4()
    event_digest = digest_run_event(
        migration_run_uuid=run_uuid,
        sequence_number=1,
        event_type="run_queued",
        state_before=None,
        state_after="queued",
        evidence=canonical_evidence,
        actor_user_uuid=requested_by_user_uuid,
        created_at=transition_time,
        previous_event_digest=None,
    )
    result = await session.execute(
        insert(MigrationRun)
        .values(
            migration_run_uuid=run_uuid,
            project_space_uuid=plan.project_space_uuid,
            migration_plan_uuid=plan.migration_plan_uuid,
            run_kind=run_kind,
            state="queued",
            state_version=1,
            idempotency_key_hash=key_hash,
            plan_digest=plan.statement_digest,
            request_digest=request_digest,
            latest_event_digest=event_digest,
            requested_by_user_uuid=requested_by_user_uuid,
            cancellation_requested=False,
            observed_base_digest=None,
            evidence_json=canonical_evidence,
            error_code=None,
            created_at=transition_time,
            updated_at=transition_time,
            started_at=None,
            finished_at=None,
        )
        .on_conflict_do_nothing(constraint="uq_migration_run__idempotent_action")
        .returning(MigrationRun.migration_run_uuid)
    )
    inserted_uuid = result.scalar_one_or_none()
    if inserted_uuid is None:
        existing = await session.scalar(
            select(MigrationRun).where(
                MigrationRun.project_space_uuid == plan.project_space_uuid,
                MigrationRun.run_kind == run_kind,
                MigrationRun.idempotency_key_hash == key_hash,
            )
        )
        if existing is None:
            raise MigrationRunContractError("idempotency winner is unavailable")
        if existing.request_digest != request_digest:
            raise MigrationRunContractError("idempotency key conflict")
        return MigrationRunCreation(
            migration_run_uuid=existing.migration_run_uuid,
            state=existing.state,
            state_version=existing.state_version,
            reused=True,
        )

    session.add(
        MigrationRunEvent(
            migration_run_event_uuid=uuid.uuid4(),
            migration_run_uuid=inserted_uuid,
            sequence_number=1,
            event_type="run_queued",
            state_before=None,
            state_after="queued",
            evidence_json=canonical_evidence,
            previous_event_digest=None,
            event_digest=event_digest,
            actor_user_uuid=requested_by_user_uuid,
            created_at=transition_time,
        )
    )
    return MigrationRunCreation(
        migration_run_uuid=inserted_uuid,
        state="queued",
        state_version=1,
        reused=False,
    )


async def transition_migration_run(
    session: AsyncSession,
    *,
    migration_run_uuid: uuid.UUID,
    expected_state_version: int,
    next_state: str,
    event_type: str,
    evidence: Mapping[str, object],
    actor_user_uuid: uuid.UUID | None,
    now: dt.datetime | None = None,
) -> MigrationRunTransition:
    """Atomically advance one run and append the same-version durable event.

    The caller owns the surrounding transaction. The compare-and-swap update
    prevents stale workers from publishing evidence after another worker has
    advanced the run. Any later event insert failure therefore rolls the state
    update back with the caller's transaction.
    """

    if (
        isinstance(expected_state_version, bool)
        or not isinstance(expected_state_version, int)
        or expected_state_version < 1
    ):
        raise MigrationRunContractError("expected state version is invalid")
    if _EVENT_TYPE.fullmatch(event_type) is None:
        raise MigrationRunContractError("event type is invalid")
    canonical_evidence = canonicalize_run_evidence(evidence)
    transition_time = now or dt.datetime.now(dt.timezone.utc)
    if transition_time.tzinfo is None or transition_time.utcoffset() is None:
        raise MigrationRunContractError("transition time must include a timezone")

    run = await session.scalar(
        select(MigrationRun)
        .where(MigrationRun.migration_run_uuid == migration_run_uuid)
        .execution_options(populate_existing=True)
    )
    if run is None or run.state_version != expected_state_version:
        raise MigrationRunContractError("migration run state version conflict")

    validate_run_transition(run.run_kind, run.state, next_state)
    next_version = expected_state_version + 1
    previous_event_digest = run.latest_event_digest
    event_digest = digest_run_event(
        migration_run_uuid=migration_run_uuid,
        sequence_number=next_version,
        event_type=event_type,
        state_before=run.state,
        state_after=next_state,
        evidence=canonical_evidence,
        actor_user_uuid=actor_user_uuid,
        created_at=transition_time,
        previous_event_digest=previous_event_digest,
    )
    started_at = run.started_at
    finished_at = run.finished_at
    values: dict[str, object] = {
        "state": next_state,
        "state_version": next_version,
        "evidence_json": canonical_evidence,
        "latest_event_digest": event_digest,
        "updated_at": transition_time,
    }
    if run.state == "queued" and started_at is None:
        started_at = transition_time
        values["started_at"] = started_at
    if not _TRANSITIONS[run.run_kind].get(next_state):
        finished_at = transition_time
        values["finished_at"] = finished_at

    result = cast(
        CursorResult[Any],
        await session.execute(
            update(MigrationRun)
            .where(
                MigrationRun.migration_run_uuid == migration_run_uuid,
                MigrationRun.run_kind == run.run_kind,
                MigrationRun.state == run.state,
                MigrationRun.state_version == expected_state_version,
                MigrationRun.latest_event_digest == previous_event_digest,
            )
            .values(**values)
            .execution_options(synchronize_session=False)
        ),
    )
    if result.rowcount != 1:
        raise MigrationRunContractError("migration run state version conflict")

    session.add(
        MigrationRunEvent(
            migration_run_event_uuid=uuid.uuid4(),
            migration_run_uuid=migration_run_uuid,
            sequence_number=next_version,
            event_type=event_type,
            state_before=run.state,
            state_after=next_state,
            evidence_json=canonical_evidence,
            previous_event_digest=previous_event_digest,
            event_digest=event_digest,
            actor_user_uuid=actor_user_uuid,
            created_at=transition_time,
        )
    )
    return MigrationRunTransition(
        state=next_state,
        state_version=next_version,
        started_at=started_at,
        finished_at=finished_at,
    )


async def request_migration_run_cancellation(
    session: AsyncSession,
    *,
    migration_run_uuid: uuid.UUID,
    expected_state_version: int,
    actor_user_uuid: uuid.UUID | None,
    evidence: Mapping[str, object],
    now: dt.datetime | None = None,
) -> MigrationRunCancellation:
    """Persist cancellation intent without inventing a synthetic run state.

    Cancellation increments the same optimistic state version used by workers
    and appends a same-state event. A worker must therefore observe the intent
    before its next transition can win. The caller owns the transaction.
    """

    if (
        isinstance(expected_state_version, bool)
        or not isinstance(expected_state_version, int)
        or expected_state_version < 1
    ):
        raise MigrationRunContractError("expected state version is invalid")
    canonical_evidence = canonicalize_run_evidence(evidence)
    request_time = now or dt.datetime.now(dt.timezone.utc)
    if request_time.tzinfo is None or request_time.utcoffset() is None:
        raise MigrationRunContractError("cancellation time must include a timezone")

    run = await session.scalar(
        select(MigrationRun)
        .where(MigrationRun.migration_run_uuid == migration_run_uuid)
        .execution_options(populate_existing=True)
    )
    if run is None or run.state_version != expected_state_version:
        raise MigrationRunContractError("migration run state version conflict")
    transitions = _TRANSITIONS.get(run.run_kind)
    if transitions is None or run.state not in (
        DRY_RUN_STATES if run.run_kind == "dry_run" else APPLY_RUN_STATES
    ):
        raise MigrationRunContractError("migration run state is invalid")
    if not transitions.get(run.state):
        raise MigrationRunContractError("terminal migration run cannot be cancelled")
    if run.cancellation_requested:
        return MigrationRunCancellation(
            state=run.state,
            state_version=run.state_version,
            reused=True,
        )

    next_version = expected_state_version + 1
    previous_event_digest = run.latest_event_digest
    event_digest = digest_run_event(
        migration_run_uuid=migration_run_uuid,
        sequence_number=next_version,
        event_type="cancellation_requested",
        state_before=run.state,
        state_after=run.state,
        evidence=canonical_evidence,
        actor_user_uuid=actor_user_uuid,
        created_at=request_time,
        previous_event_digest=previous_event_digest,
    )
    result = cast(
        CursorResult[Any],
        await session.execute(
            update(MigrationRun)
            .where(
                MigrationRun.migration_run_uuid == migration_run_uuid,
                MigrationRun.run_kind == run.run_kind,
                MigrationRun.state == run.state,
                MigrationRun.state_version == expected_state_version,
                MigrationRun.cancellation_requested.is_(False),
                MigrationRun.latest_event_digest == previous_event_digest,
            )
            .values(
                cancellation_requested=True,
                state_version=next_version,
                updated_at=request_time,
                latest_event_digest=event_digest,
            )
            .execution_options(synchronize_session=False)
        ),
    )
    if result.rowcount != 1:
        raise MigrationRunContractError("migration run state version conflict")

    session.add(
        MigrationRunEvent(
            migration_run_event_uuid=uuid.uuid4(),
            migration_run_uuid=migration_run_uuid,
            sequence_number=next_version,
            event_type="cancellation_requested",
            state_before=run.state,
            state_after=run.state,
            evidence_json=canonical_evidence,
            previous_event_digest=previous_event_digest,
            event_digest=event_digest,
            actor_user_uuid=actor_user_uuid,
            created_at=request_time,
        )
    )
    return MigrationRunCancellation(
        state=run.state,
        state_version=next_version,
        reused=False,
    )
