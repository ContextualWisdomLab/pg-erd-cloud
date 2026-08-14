"""Compile an immutable plan into target-free apply revalidation inputs.

This module binds the persisted plan digest and compatibility metadata to the
existing structured table-lock and live-precondition compilers.  It also proves
that every data precondition names its statement's table and that the table is
present in the deterministic lock set.  A future executor must acquire those
locks and then perform fresh snapshot comparison and these checks on the same
connection before DDL.

The boundary opens no target connection, acquires no lock, captures no
snapshot, checks no privilege, dispatches no work, and executes no SQL or DDL.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from app.forward.apply_lock_plan import (
    ApplyLockPlanContractError,
    ApplyLockTarget,
    compile_apply_lock_targets,
)
from app.forward.live_preflight import (
    LivePreflightContractError,
    LivePreflightQuery,
    compile_live_preflight_queries,
)
from app.forward.migration_plan import COMPILER_VERSION, verify_migration_plan_digest
from app.pg_introspect.snapshot_contract import (
    CURRENT_POSTGRES_SNAPSHOT_CONTRACT_VERSION,
)

_DIGEST_RE = re.compile(r"[0-9a-f]{64}")
_PLAN_FIELDS = frozenset(
    {
        "compiler_version",
        "snapshot_contract_version",
        "postgresql_major",
        "base_digest",
        "target_digest",
        "statements",
        "proposed_statements",
        "blockers",
        "risk_summary",
        "requires_destructive_confirmation",
        "can_dry_run",
        "plan_digest",
    }
)
_STATEMENT_FIELDS = frozenset(
    {
        "kind",
        "target",
        "object_ref",
        "sql",
        "transactional",
        "dependencies",
        "dependency_refs",
        "reversible",
        "risk",
        "required_privileges",
        "preconditions",
    }
)


class PreApplyRevalidationContractError(ValueError):
    """Reject input that cannot safely enter future in-lock revalidation."""


@dataclass(frozen=True)
class PreApplyRevalidationManifest:
    """Immutable inputs a future executor must revalidate after locking."""

    plan_digest: str
    compiler_version: str
    snapshot_contract_version: int
    postgresql_major: int
    base_digest: str
    target_digest: str
    lock_targets: tuple[ApplyLockTarget, ...]
    precondition_queries: tuple[LivePreflightQuery, ...]


def _require_digest(value: object, *, name: str) -> str:
    """Return one canonical lowercase SHA-256 digest."""

    if not isinstance(value, str) or _DIGEST_RE.fullmatch(value) is None:
        raise PreApplyRevalidationContractError(f"{name} is invalid")
    return value


def _validate_plan_shape(plan: Mapping[str, object]) -> list[object]:
    """Reject contract drift before delegating to bounded compilers."""

    if set(plan) != _PLAN_FIELDS:
        raise PreApplyRevalidationContractError(
            "pre-apply revalidation plan contract is invalid"
        )
    statements = plan.get("statements")
    if not isinstance(statements, list):
        raise PreApplyRevalidationContractError(
            "pre-apply revalidation statements are invalid"
        )
    for statement in statements:
        if not isinstance(statement, Mapping) or set(statement) != _STATEMENT_FIELDS:
            raise PreApplyRevalidationContractError(
                "pre-apply revalidation statement contract is invalid"
            )
    if plan.get("compiler_version") != COMPILER_VERSION:
        raise PreApplyRevalidationContractError(
            "pre-apply revalidation compiler is unsupported"
        )
    if (
        plan.get("snapshot_contract_version")
        != CURRENT_POSTGRES_SNAPSHOT_CONTRACT_VERSION
    ):
        raise PreApplyRevalidationContractError(
            "pre-apply revalidation snapshot contract is unsupported"
        )
    if plan.get("proposed_statements") != []:
        raise PreApplyRevalidationContractError(
            "pre-apply revalidation proposals are not executable"
        )
    return cast(list[object], statements)


def _validate_locked_preconditions(
    statements: list[object],
    lock_targets: tuple[ApplyLockTarget, ...],
) -> None:
    """Require each data precondition to be covered by its statement lock."""

    locked_tables = {
        (target.schema_name, target.table_name) for target in lock_targets
    }
    for statement in statements:
        if not isinstance(statement, Mapping):  # guarded by _validate_plan_shape
            raise PreApplyRevalidationContractError(
                "pre-apply revalidation statement contract is invalid"
            )
        object_ref = statement.get("object_ref")
        preconditions = statement.get("preconditions")
        if not isinstance(object_ref, Mapping) or not isinstance(preconditions, list):
            raise PreApplyRevalidationContractError(
                "pre-apply revalidation statement contract is invalid"
            )
        statement_table = (
            object_ref.get("schema_name"),
            object_ref.get("table_name"),
        )
        for precondition in preconditions:
            if not isinstance(precondition, Mapping):
                raise PreApplyRevalidationContractError(
                    "pre-apply revalidation precondition is invalid"
                )
            precondition_table = (
                precondition.get("schema_name"),
                precondition.get("table_name"),
            )
            if precondition_table != statement_table:
                raise PreApplyRevalidationContractError(
                    "pre-apply revalidation precondition target "
                    "does not match statement"
                )
            if precondition_table not in locked_tables:
                raise PreApplyRevalidationContractError(
                    "pre-apply revalidation precondition target is not locked"
                )


def compile_pre_apply_revalidation_manifest(
    plan: Mapping[str, object],
    *,
    expected_plan_digest: object,
) -> PreApplyRevalidationManifest:
    """Bind exact signed plan metadata to deterministic lock/check inputs.

    The returned value defines inputs only.  It does not make holding the locks
    or completing revalidation true and therefore grants no execution authority.
    """

    expected_digest = _require_digest(
        expected_plan_digest, name="expected plan digest"
    )
    try:
        digest_is_valid = isinstance(plan, Mapping) and verify_migration_plan_digest(
            plan, expected_digest
        )
    except (TypeError, ValueError, OverflowError, RecursionError):
        digest_is_valid = False
    if not digest_is_valid:
        raise PreApplyRevalidationContractError(
            "pre-apply revalidation plan digest is invalid"
        )
    statements = _validate_plan_shape(plan)

    postgresql_major = plan.get("postgresql_major")
    if (
        not isinstance(postgresql_major, int)
        or isinstance(postgresql_major, bool)
        or postgresql_major < 14
        or postgresql_major > 18
    ):
        raise PreApplyRevalidationContractError(
            "pre-apply revalidation PostgreSQL major is invalid"
        )
    base_digest = _require_digest(plan.get("base_digest"), name="base digest")
    target_digest = _require_digest(
        plan.get("target_digest"), name="target digest"
    )

    try:
        lock_targets = compile_apply_lock_targets(plan)
        precondition_queries = compile_live_preflight_queries(plan)
    except (ApplyLockPlanContractError, LivePreflightContractError) as err:
        raise PreApplyRevalidationContractError(str(err)) from None
    _validate_locked_preconditions(statements, lock_targets)

    return PreApplyRevalidationManifest(
        plan_digest=expected_digest,
        compiler_version=COMPILER_VERSION,
        snapshot_contract_version=CURRENT_POSTGRES_SNAPSHOT_CONTRACT_VERSION,
        postgresql_major=postgresql_major,
        base_digest=base_digest,
        target_digest=target_digest,
        lock_targets=lock_targets,
        precondition_queries=precondition_queries,
    )
