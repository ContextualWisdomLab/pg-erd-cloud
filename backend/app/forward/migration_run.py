"""Durable migration-run state and evidence contracts.

This module persists an execution-free dispatch outbox but remains independent
from queue delivery. It defines the states that may become durable product
evidence, hashes caller idempotency keys, and prevents raw SQL or
credential-bearing fields from entering run events.
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
from sqlalchemy.orm.attributes import set_committed_value

from app.forward.isolated_dry_run import MAX_DRY_RUN_STATEMENTS
from app.forward.live_preflight import (
    LIVE_PREFLIGHT_PRECONDITION_KINDS,
    MAX_LIVE_PREFLIGHT_QUERIES,
)
from app.forward.migration_plan import verify_migration_plan_digest
from app.models import (
    MigrationPlan,
    MigrationRun,
    MigrationRunDispatch,
    MigrationRunEvent,
)

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
_LIVE_PREFLIGHT_RESULT_FIELDS = frozenset(
    {
        "preconditions_passed",
        "checks",
        "observed_base_digest",
        "matches_plan_base",
    }
)
_LIVE_PREFLIGHT_CHECK_FIELDS = frozenset(
    {"statement_index", "precondition_index", "kind", "passed"}
)
_ISOLATED_DRY_RUN_RESULT_FIELDS = frozenset(
    {
        "postgresql_major",
        "statement_count",
        "base_digest",
        "target_digest",
        "converged",
    }
)


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
    cancellation_requested: bool
    reused: bool


@dataclass(frozen=True)
class MigrationDispatchClaim:
    """Identifier-only relay claim held by the caller's open transaction."""

    migration_run_dispatch_uuid: uuid.UUID
    migration_run_uuid: uuid.UUID
    dispatch_kind: str
    attempt_count: int


@dataclass(frozen=True)
class MigrationRunCancellation:
    """The durable cancellation-intent identity selected by one CAS request."""

    state: str
    state_version: int
    reused: bool


def _require_aware_dispatch_time(value: dt.datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise MigrationRunContractError("dispatch time must include a timezone")


async def claim_one_migration_dispatch(
    session: AsyncSession,
    *,
    now: dt.datetime | None = None,
) -> MigrationDispatchClaim | None:
    """Lock one due outbox row for an identifier-only publish attempt.

    The caller must keep this transaction open while publishing only the
    migration-run UUID, then mark the claim published before committing. A
    publish failure must roll back the transaction, restoring the pending row
    and its attempt counter. SKIP LOCKED lets independent relays make progress
    without publishing the same row concurrently.
    """

    transition_time = now or dt.datetime.now(dt.timezone.utc)
    _require_aware_dispatch_time(transition_time)
    dispatch = await session.scalar(
        select(MigrationRunDispatch)
        .where(
            MigrationRunDispatch.status == "pending",
            MigrationRunDispatch.not_before <= transition_time,
        )
        .order_by(
            MigrationRunDispatch.not_before,
            MigrationRunDispatch.migration_run_dispatch_uuid,
        )
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if dispatch is None:
        return None
    dispatch.attempt_count = int(dispatch.attempt_count) + 1
    return MigrationDispatchClaim(
        migration_run_dispatch_uuid=dispatch.migration_run_dispatch_uuid,
        migration_run_uuid=dispatch.migration_run_uuid,
        dispatch_kind=dispatch.dispatch_kind,
        attempt_count=dispatch.attempt_count,
    )


async def mark_migration_dispatch_published(
    session: AsyncSession,
    *,
    claim: MigrationDispatchClaim,
    now: dt.datetime | None = None,
) -> None:
    """CAS one locked claim to published without committing its transaction."""

    transition_time = now or dt.datetime.now(dt.timezone.utc)
    _require_aware_dispatch_time(transition_time)
    if claim.attempt_count < 1:
        raise MigrationRunContractError("migration dispatch attempt is invalid")
    result = cast(
        CursorResult[Any],
        await session.execute(
            update(MigrationRunDispatch)
            .where(
                MigrationRunDispatch.migration_run_dispatch_uuid
                == claim.migration_run_dispatch_uuid,
                MigrationRunDispatch.migration_run_uuid
                == claim.migration_run_uuid,
                MigrationRunDispatch.dispatch_kind == claim.dispatch_kind,
                MigrationRunDispatch.status == "pending",
                MigrationRunDispatch.attempt_count == claim.attempt_count,
                MigrationRunDispatch.published_at.is_(None),
            )
            .values(status="published", published_at=transition_time)
            .execution_options(synchronize_session=False)
        ),
    )
    if result.rowcount != 1:
        raise MigrationRunContractError("migration dispatch claim is stale")


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


def _evidence_field_tokens(key: str) -> tuple[str, ...]:
    separated_key = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
    return tuple(
        token
        for token in re.split(r"[^a-z0-9]+", separated_key.casefold())
        if token
    )


def _contains_evidence_field(value: object, identity: str) -> bool:
    if isinstance(value, Mapping):
        return any(
            "".join(_evidence_field_tokens(key)) == identity
            or _contains_evidence_field(nested, identity)
            for key, nested in value.items()
            if isinstance(key, str)
        )
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return any(_contains_evidence_field(item, identity) for item in value)
    return False


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
            tokens = set(_evidence_field_tokens(key))
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

    The PostgreSQL uniqueness constraint is the concurrency winner. A new run,
    its genesis event, and one identifier-only dispatch outbox row share the
    caller's transaction. This function never commits, publishes, or signals a
    worker. Apply creation remains fail-closed until approval and passed-dry-run
    bindings are persisted.
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
            cancellation_requested=existing.cancellation_requested,
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
    session.add(
        MigrationRunDispatch(
            migration_run_dispatch_uuid=uuid.uuid4(),
            migration_run_uuid=inserted_uuid,
            dispatch_kind="isolated_dry_run",
            status="pending",
            attempt_count=0,
            not_before=transition_time,
            created_at=transition_time,
            published_at=None,
        )
    )
    return MigrationRunCreation(
        migration_run_uuid=inserted_uuid,
        state="queued",
        state_version=1,
        cancellation_requested=False,
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
    observed_base_digest: str | None = None,
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
    if observed_base_digest is not None and _HEX_DIGEST.fullmatch(
        observed_base_digest
    ) is None:
        raise MigrationRunContractError("observed base digest is invalid")
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

    current_state = run.state
    validate_run_transition(run.run_kind, current_state, next_state)
    binds_observed_base = (
        current_state == "live_preflight_running"
        and next_state in {"passed", "drifted"}
    )
    if binds_observed_base:
        if observed_base_digest is None:
            raise MigrationRunContractError("observed base digest is required")
        if _contains_evidence_field(canonical_evidence, "observedbasedigest"):
            raise MigrationRunContractError(
                "observed base digest evidence is server-authoritative"
            )
        plan = await session.scalar(
            select(MigrationPlan).where(
                MigrationPlan.migration_plan_uuid == run.migration_plan_uuid
            )
        )
        if (
            plan is None
            or plan.project_space_uuid != run.project_space_uuid
            or run.plan_digest != plan.statement_digest
            or not verify_migration_plan_digest(
                plan.plan_json, plan.statement_digest
            )
            or plan.plan_json.get("compiler_version") != plan.compiler_version
            or plan.plan_json.get("base_digest") != plan.base_digest
            or plan.plan_json.get("target_digest") != plan.target_digest
        ):
            raise MigrationRunContractError(
                "migration plan integrity verification failed"
            )
        matches_planned_base = observed_base_digest == plan.base_digest
        if (next_state == "passed") != matches_planned_base:
            raise MigrationRunContractError(
                "observed base digest conflicts with preflight outcome"
            )
        canonical_evidence = canonicalize_run_evidence(
            {
                **canonical_evidence,
                "observed_base_digest": observed_base_digest,
            }
        )
    elif observed_base_digest is not None:
        raise MigrationRunContractError(
            "observed base digest is not allowed for this transition"
        )
    next_version = expected_state_version + 1
    previous_event_digest = run.latest_event_digest
    event_digest = digest_run_event(
        migration_run_uuid=migration_run_uuid,
        sequence_number=next_version,
        event_type=event_type,
        state_before=current_state,
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
    if current_state == "queued" and started_at is None:
        started_at = transition_time
        values["started_at"] = started_at
    if not _TRANSITIONS[run.run_kind].get(next_state):
        finished_at = transition_time
        values["finished_at"] = finished_at
    if binds_observed_base:
        values["observed_base_digest"] = observed_base_digest

    result = cast(
        CursorResult[Any],
        await session.execute(
            update(MigrationRun)
            .where(
                MigrationRun.migration_run_uuid == migration_run_uuid,
                MigrationRun.run_kind == run.run_kind,
                MigrationRun.state == current_state,
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
            state_before=current_state,
            state_after=next_state,
            evidence_json=canonical_evidence,
            previous_event_digest=previous_event_digest,
            event_digest=event_digest,
            actor_user_uuid=actor_user_uuid,
            created_at=transition_time,
        )
    )
    for attribute, value in values.items():
        set_committed_value(run, attribute, value)
    return MigrationRunTransition(
        state=next_state,
        state_version=next_version,
        started_at=started_at,
        finished_at=finished_at,
    )


def _canonicalize_isolated_dry_run_result(
    result: Mapping[str, object],
) -> tuple[int, int, str, str]:
    """Validate the exact bounded success shape returned by the executor."""

    if (
        not isinstance(result, Mapping)
        or set(result) != _ISOLATED_DRY_RUN_RESULT_FIELDS
    ):
        raise MigrationRunContractError("isolated dry-run result is invalid")
    postgresql_major = result["postgresql_major"]
    statement_count = result["statement_count"]
    base_digest = result["base_digest"]
    target_digest = result["target_digest"]
    if (
        isinstance(postgresql_major, bool)
        or not isinstance(postgresql_major, int)
        or postgresql_major < 14
        or postgresql_major > 18
        or isinstance(statement_count, bool)
        or not isinstance(statement_count, int)
        or statement_count < 0
        or statement_count > MAX_DRY_RUN_STATEMENTS
        or not isinstance(base_digest, str)
        or _HEX_DIGEST.fullmatch(base_digest) is None
        or not isinstance(target_digest, str)
        or _HEX_DIGEST.fullmatch(target_digest) is None
        or result["converged"] is not True
    ):
        raise MigrationRunContractError("isolated dry-run result is invalid")
    return postgresql_major, statement_count, base_digest, target_digest


async def complete_isolated_dry_run(
    session: AsyncSession,
    *,
    migration_run_uuid: uuid.UUID,
    expected_state_version: int,
    result: Mapping[str, object],
    actor_user_uuid: uuid.UUID | None,
    now: dt.datetime | None = None,
) -> MigrationRunTransition:
    """Verify one executor success against its stored plan and advance CAS.

    The caller cannot select the next state, event type, evidence shape, plan,
    or digests. This boundary owns no sandbox, connection, credential, queue
    lease, durable worker attempt, or DDL execution authority.
    """

    postgresql_major, statement_count, base_digest, target_digest = (
        _canonicalize_isolated_dry_run_result(result)
    )
    transition_time = now or dt.datetime.now(dt.timezone.utc)
    if transition_time.tzinfo is None or transition_time.utcoffset() is None:
        raise MigrationRunContractError("transition time must include a timezone")
    run = await session.scalar(
        select(MigrationRun).where(
            MigrationRun.migration_run_uuid == migration_run_uuid
        )
    )
    if (
        run is None
        or run.run_kind != "dry_run"
        or run.state != "sandbox_running"
        or run.state_version != expected_state_version
        or run.cancellation_requested
    ):
        raise MigrationRunContractError("migration run state version conflict")
    plan = await session.scalar(
        select(MigrationPlan).where(
            MigrationPlan.migration_plan_uuid == run.migration_plan_uuid
        )
    )
    if (
        plan is None
        or plan.project_space_uuid != run.project_space_uuid
        or run.plan_digest != plan.statement_digest
        or plan.expires_at <= transition_time
        or not verify_migration_plan_digest(plan.plan_json, plan.statement_digest)
        or plan.plan_json.get("compiler_version") != plan.compiler_version
        or plan.plan_json.get("base_digest") != plan.base_digest
        or plan.plan_json.get("target_digest") != plan.target_digest
    ):
        raise MigrationRunContractError(
            "migration plan integrity verification failed"
        )
    statements = plan.plan_json.get("statements")
    if not isinstance(statements, list) or (
        postgresql_major != plan.plan_json.get("postgresql_major")
        or statement_count != len(statements)
        or base_digest != plan.base_digest
        or target_digest != plan.target_digest
    ):
        raise MigrationRunContractError(
            "isolated dry-run result does not match migration plan"
        )
    return await transition_migration_run(
        session,
        migration_run_uuid=migration_run_uuid,
        expected_state_version=expected_state_version,
        next_state="live_preflight_running",
        event_type="isolated_dry_run_succeeded",
        evidence={
            "postgresql_major": postgresql_major,
            "statement_count": statement_count,
            "converged": True,
        },
        actor_user_uuid=actor_user_uuid,
        now=now,
    )


def _canonicalize_live_preflight_result(
    result: Mapping[str, object],
) -> tuple[bool, bool, str, int, int]:
    """Validate one exact execution result without retaining target metadata."""

    if (
        not isinstance(result, Mapping)
        or set(result) != _LIVE_PREFLIGHT_RESULT_FIELDS
    ):
        raise MigrationRunContractError("live preflight result is invalid")
    preconditions_passed = result["preconditions_passed"]
    matches_plan_base = result["matches_plan_base"]
    observed_base_digest = result["observed_base_digest"]
    checks = result["checks"]
    if (
        not isinstance(preconditions_passed, bool)
        or not isinstance(matches_plan_base, bool)
        or not isinstance(observed_base_digest, str)
        or _HEX_DIGEST.fullmatch(observed_base_digest) is None
        or not isinstance(checks, list)
        or len(checks) > MAX_LIVE_PREFLIGHT_QUERIES
    ):
        raise MigrationRunContractError("live preflight result is invalid")
    failed_check_count = 0
    positions: set[tuple[int, int]] = set()
    for check in checks:
        if not isinstance(check, Mapping) or set(check) != _LIVE_PREFLIGHT_CHECK_FIELDS:
            raise MigrationRunContractError("live preflight result is invalid")
        statement_index = check["statement_index"]
        precondition_index = check["precondition_index"]
        kind = check["kind"]
        passed = check["passed"]
        if (
            isinstance(statement_index, bool)
            or not isinstance(statement_index, int)
            or statement_index < 0
            or isinstance(precondition_index, bool)
            or not isinstance(precondition_index, int)
            or precondition_index < 0
            or not isinstance(kind, str)
            or kind not in LIVE_PREFLIGHT_PRECONDITION_KINDS
            or not isinstance(passed, bool)
        ):
            raise MigrationRunContractError("live preflight result is invalid")
        position = (statement_index, precondition_index)
        if position in positions:
            raise MigrationRunContractError("live preflight result is invalid")
        positions.add(position)
        if not passed:
            failed_check_count += 1
    if preconditions_passed != (failed_check_count == 0):
        raise MigrationRunContractError("live preflight result is invalid")
    return (
        preconditions_passed,
        matches_plan_base,
        observed_base_digest,
        len(checks),
        failed_check_count,
    )


async def complete_live_preflight(
    session: AsyncSession,
    *,
    migration_run_uuid: uuid.UUID,
    expected_state_version: int,
    result: Mapping[str, object],
    actor_user_uuid: uuid.UUID | None,
    now: dt.datetime | None = None,
) -> MigrationRunTransition:
    """Derive and persist one terminal state from bounded preflight evidence.

    A caller cannot choose the terminal state, event type, observed digest, or
    durable evidence shape. Base mismatch wins ``drifted`` classification;
    otherwise any failed structured check becomes ``failed`` and only an exact
    base match with every check passing becomes ``passed``.
    """

    (
        preconditions_passed,
        matches_plan_base,
        observed_base_digest,
        check_count,
        failed_check_count,
    ) = _canonicalize_live_preflight_result(result)
    if not matches_plan_base:
        next_state = "drifted"
    elif preconditions_passed:
        next_state = "passed"
    else:
        next_state = "failed"
    return await transition_migration_run(
        session,
        migration_run_uuid=migration_run_uuid,
        expected_state_version=expected_state_version,
        next_state=next_state,
        event_type=f"live_preflight_{next_state}",
        evidence={
            "check_count": check_count,
            "failed_check_count": failed_check_count,
        },
        observed_base_digest=(
            observed_base_digest if next_state in {"passed", "drifted"} else None
        ),
        actor_user_uuid=actor_user_uuid,
        now=now,
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
    for attribute, value in {
        "cancellation_requested": True,
        "state_version": next_version,
        "updated_at": request_time,
        "latest_event_digest": event_digest,
    }.items():
        set_committed_value(run, attribute, value)
    return MigrationRunCancellation(
        state=run.state,
        state_version=next_version,
        reused=False,
    )
