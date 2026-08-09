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
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MigrationRun, MigrationRunEvent

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


class MigrationRunContractError(ValueError):
    """Raised when run state or durable evidence violates the v1 contract."""


@dataclass(frozen=True)
class MigrationRunTransition:
    """The durable state identity produced by one successful CAS transition."""

    state: str
    state_version: int
    started_at: dt.datetime | None
    finished_at: dt.datetime | None


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
    if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", event_type) is None:
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
    started_at = run.started_at
    finished_at = run.finished_at
    values: dict[str, object] = {
        "state": next_state,
        "state_version": next_version,
        "evidence_json": canonical_evidence,
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
