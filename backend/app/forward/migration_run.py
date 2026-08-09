"""Durable migration-run state and evidence contracts.

This module is deliberately independent from queue delivery. It defines the
states that may become durable product evidence, hashes caller idempotency keys,
and prevents raw SQL or credential-bearing fields from entering run events.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

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


class MigrationRunContractError(ValueError):
    """Raised when run state or durable evidence violates the v1 contract."""


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


def _validate_evidence(value: object, *, path: str, depth: int) -> Any:
    if depth > MAX_RUN_EVIDENCE_DEPTH:
        raise MigrationRunContractError("run evidence nesting is too deep")
    if value is None or isinstance(value, (bool, int, str)):
        if isinstance(value, str) and len(value.encode("utf-8")) > MAX_RUN_EVIDENCE_STRING_BYTES:
            raise MigrationRunContractError("run evidence string is too large")
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
            tokens = {
                token
                for token in re.split(r"[^a-z0-9]+", key.casefold())
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
    loaded = json.loads(encoded)
    if not isinstance(loaded, dict):
        raise MigrationRunContractError("run evidence must be an object")
    return loaded
