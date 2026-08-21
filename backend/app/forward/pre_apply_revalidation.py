"""Compile and capture bounded pre-apply revalidation facts.

This module binds the persisted plan digest and compatibility metadata to the
existing structured table-lock and live-precondition compilers.  It also proves
that every data precondition names its statement's table and that the table is
present in the deterministic lock set.  Its pure observation assessment rejects
missing, extra, or positionally mismatched caller evidence and derives only
non-authorizing booleans.  The public compiler re-derives the manifest from the
exact signed plan rather than trusting a caller-built dataclass. The manifest,
probe compiler, and pure assessor open no target connection. The optional
capture primitive accepts a caller-owned connection and performs only fixed
reads in one read-only repeatable-read transaction, producing non-authorizing
facts. It acquires no advisory/object lock, owns no credential or durable
attempt binding, dispatches no work, and executes no DDL. A future executor must
repeat these checks after acquiring its locks on the bound execution connection.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

import asyncpg
from asyncpg.transaction import Transaction

from app.forward.apply_lock_plan import (
    ApplyLockPlanContractError,
    ApplyLockTarget,
    compile_apply_lock_targets,
)
from app.forward.live_preflight import (
    LivePreflightContractError,
    LivePreflightQuery,
    SnapshotCapture,
    compare_live_preflight_snapshot,
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
_OBSERVATION_FIELDS = frozenset(
    {"plan_digest", "observed_base_digest", "privileges", "preconditions"}
)
_PRIVILEGE_OBSERVATION_FIELDS = frozenset(
    {
        "statement_index",
        "privilege",
        "scope",
        "schema_name",
        "table_name",
        "allowed",
    }
)
_PRECONDITION_OBSERVATION_FIELDS = frozenset(
    {"statement_index", "precondition_index", "kind", "passed"}
)
MAX_PRE_APPLY_REVALIDATION_STATEMENT_TIMEOUT_MS = 60_000


class PreApplyRevalidationContractError(ValueError):
    """Reject input that cannot safely enter future in-lock revalidation."""


class _PreApplyRevalidationCaptureFailure(Exception):
    """Separate target/callback failures from fixed public diagnostics."""


@dataclass(frozen=True)
class ApplyTransactionSegment:
    """One ordered compiler-v1 all-transactional apply segment input."""

    segment_index: int
    statement_indexes: tuple[int, ...]
    transactional: bool


@dataclass(frozen=True)
class ApplyPrivilegeRequirement:
    """One compiler-v1 privilege requirement without target access."""

    statement_index: int
    privilege: str
    scope: str
    schema_name: str | None
    table_name: str | None


@dataclass(frozen=True)
class ApplyPrivilegeQuery:
    """One parameterized read-only PostgreSQL privilege probe."""

    statement_index: int
    privilege: str
    scope: str
    sql: str
    parameters: tuple[str, ...]


@dataclass(frozen=True)
class PreApplyRevalidationManifest:
    """Immutable inputs a future executor must revalidate after locking."""

    plan_digest: str
    compiler_version: str
    snapshot_contract_version: int
    postgresql_major: int
    base_digest: str
    target_digest: str
    transaction_segments: tuple[ApplyTransactionSegment, ...]
    privilege_requirements: tuple[ApplyPrivilegeRequirement, ...]
    lock_targets: tuple[ApplyLockTarget, ...]
    precondition_queries: tuple[LivePreflightQuery, ...]


@dataclass(frozen=True)
class PreApplyRevalidationAssessment:
    """Execution-neutral assessment of complete, manifest-bound observations."""

    observed_base_digest: str
    base_matches: bool
    privileges_satisfied: bool
    preconditions_satisfied: bool


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


def _compile_transaction_segments(
    statements: list[object],
) -> tuple[ApplyTransactionSegment, ...]:
    """Represent compiler-v1 work as zero or one ordered transaction segment."""

    if not statements:
        return ()
    return (
        ApplyTransactionSegment(
            segment_index=0,
            statement_indexes=tuple(range(len(statements))),
            transactional=True,
        ),
    )


def _compile_privilege_requirements(
    statements: list[object],
) -> tuple[ApplyPrivilegeRequirement, ...]:
    """Bind compiler-v1 privilege labels to structured PostgreSQL scopes."""

    requirements: list[ApplyPrivilegeRequirement] = []
    for statement_index, statement in enumerate(statements):
        if not isinstance(statement, Mapping):  # guarded by _validate_plan_shape
            raise PreApplyRevalidationContractError(
                "pre-apply revalidation statement contract is invalid"
            )
        kind = statement.get("kind")
        object_ref = statement.get("object_ref")
        if not isinstance(object_ref, Mapping):
            raise PreApplyRevalidationContractError(
                "pre-apply revalidation statement contract is invalid"
            )
        if kind == "create_schema":
            expected_privileges = ["CREATE"]
            requirement = ApplyPrivilegeRequirement(
                statement_index=statement_index,
                privilege="CREATE",
                scope="database",
                schema_name=None,
                table_name=None,
            )
        elif kind == "create_table":
            expected_privileges = ["CREATE"]
            requirement = ApplyPrivilegeRequirement(
                statement_index=statement_index,
                privilege="CREATE",
                scope="schema",
                schema_name=cast(str, object_ref.get("schema_name")),
                table_name=None,
            )
        else:
            expected_privileges = ["OWNER"]
            requirement = ApplyPrivilegeRequirement(
                statement_index=statement_index,
                privilege="OWNER",
                scope="table",
                schema_name=cast(str, object_ref.get("schema_name")),
                table_name=cast(str, object_ref.get("table_name")),
            )
        if statement.get("required_privileges") != expected_privileges:
            raise PreApplyRevalidationContractError(
                "pre-apply revalidation required privileges are invalid"
            )
        requirements.append(requirement)
    return tuple(requirements)


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
    transaction_segments = _compile_transaction_segments(statements)
    privilege_requirements = _compile_privilege_requirements(statements)

    return PreApplyRevalidationManifest(
        plan_digest=expected_digest,
        compiler_version=COMPILER_VERSION,
        snapshot_contract_version=CURRENT_POSTGRES_SNAPSHOT_CONTRACT_VERSION,
        postgresql_major=postgresql_major,
        base_digest=base_digest,
        target_digest=target_digest,
        transaction_segments=transaction_segments,
        privilege_requirements=privilege_requirements,
        lock_targets=lock_targets,
        precondition_queries=precondition_queries,
    )


def _require_privilege_identifier(value: object) -> str:
    """Validate one identifier passed as query data rather than SQL text."""

    if (
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or len(value.encode("utf-8")) > 63
    ):
        raise PreApplyRevalidationContractError(
            "pre-apply revalidation privilege identifier is invalid"
        )
    return value


def _compile_apply_privilege_queries_from_manifest(
    manifest: PreApplyRevalidationManifest,
) -> tuple[ApplyPrivilegeQuery, ...]:
    """Compile already-validated manifest requirements into catalog reads."""

    queries: list[ApplyPrivilegeQuery] = []
    for position, requirement in enumerate(manifest.privilege_requirements):
        if (
            not isinstance(requirement, ApplyPrivilegeRequirement)
            or requirement.statement_index != position
        ):
            raise PreApplyRevalidationContractError(
                "pre-apply revalidation privilege requirement order is invalid"
            )
        if (
            requirement.privilege == "CREATE"
            and requirement.scope == "database"
            and requirement.schema_name is None
            and requirement.table_name is None
        ):
            sql = (
                "SELECT pg_catalog.has_database_privilege("
                "pg_catalog.current_database(), 'CREATE')"
            )
            parameters: tuple[str, ...] = ()
        elif (
            requirement.privilege == "CREATE"
            and requirement.scope == "schema"
            and requirement.table_name is None
        ):
            schema_name = _require_privilege_identifier(requirement.schema_name)
            sql = "SELECT pg_catalog.has_schema_privilege($1::text, 'CREATE')"
            parameters = (schema_name,)
        elif requirement.privilege == "OWNER" and requirement.scope == "table":
            schema_name = _require_privilege_identifier(requirement.schema_name)
            table_name = _require_privilege_identifier(requirement.table_name)
            sql = (
                "SELECT COALESCE((SELECT pg_catalog.pg_has_role("
                "c.relowner, 'USAGE') FROM pg_catalog.pg_class AS c "
                "JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace "
                "WHERE n.nspname::text = $1::text "
                "AND c.relname::text = $2::text "
                "AND c.relkind = 'r'), FALSE)"
            )
            parameters = (schema_name, table_name)
        else:
            raise PreApplyRevalidationContractError(
                "pre-apply revalidation privilege requirement is invalid"
            )
        queries.append(
            ApplyPrivilegeQuery(
                statement_index=requirement.statement_index,
                privilege=requirement.privilege,
                scope=requirement.scope,
                sql=sql,
                parameters=parameters,
            )
        )
    return tuple(queries)


def compile_apply_privilege_queries(
    plan: Mapping[str, object],
    *,
    expected_plan_digest: object,
) -> tuple[ApplyPrivilegeQuery, ...]:
    """Compile exact signed-plan requirements into parameterized catalog reads.

    The manifest is re-derived from the exact signed plan at this public trust
    boundary.  Callers therefore cannot redirect a valid-looking requirement
    to a different database object by replacing a manifest dataclass field.

    This function does not execute the probes or establish which role,
    connection, target, transaction, or lock context produced a result.
    """

    manifest = compile_pre_apply_revalidation_manifest(
        plan,
        expected_plan_digest=expected_plan_digest,
    )
    return _compile_apply_privilege_queries_from_manifest(manifest)


async def _fetch_pre_apply_precondition(
    connection: asyncpg.Connection,
    query: LivePreflightQuery,
    *,
    client_timeout: float,
) -> object:
    """Fetch one boolean while containing expected cast-data failure."""

    if query.kind != "castable_values":
        return await connection.fetchval(
            query.sql,
            timeout=client_timeout,
        )

    savepoint = connection.transaction()
    await asyncio.wait_for(savepoint.start(), timeout=client_timeout)
    try:
        result = await connection.fetchval(
            query.sql,
            timeout=client_timeout,
        )
    except asyncpg.DataError:
        await asyncio.wait_for(savepoint.rollback(), timeout=client_timeout)
        return False
    await asyncio.wait_for(savepoint.commit(), timeout=client_timeout)
    return result


async def capture_pre_apply_revalidation_observation(
    connection: asyncpg.Connection,
    plan: Mapping[str, object],
    *,
    expected_plan_digest: object,
    capture_snapshot: SnapshotCapture,
    statement_timeout_ms: int = 5_000,
) -> PreApplyRevalidationAssessment:
    """Capture and assess fresh read-only facts in one target snapshot.

    The caller owns the connection and target routing. This bounded primitive
    re-derives the manifest from the signed plan, begins one read-only
    repeatable-read transaction, captures the strict snapshot, and observes all
    exact privilege and data-precondition positions on that same connection.
    It acquires no advisory/object lock and returns only non-authorizing facts;
    a future apply executor must repeat the checks after acquiring its locks.
    """

    if (
        not isinstance(statement_timeout_ms, int)
        or isinstance(statement_timeout_ms, bool)
        or not 1
        <= statement_timeout_ms
        <= MAX_PRE_APPLY_REVALIDATION_STATEMENT_TIMEOUT_MS
    ):
        raise PreApplyRevalidationContractError(
            "pre-apply revalidation statement timeout is invalid"
        )
    if not callable(capture_snapshot):
        raise PreApplyRevalidationContractError(
            "pre-apply revalidation snapshot capture is invalid"
        )

    manifest = compile_pre_apply_revalidation_manifest(
        plan,
        expected_plan_digest=expected_plan_digest,
    )
    privilege_queries = _compile_apply_privilege_queries_from_manifest(manifest)
    client_timeout = statement_timeout_ms / 1000 + 1
    transaction: Transaction | None = None
    transaction_started = False
    try:
        transaction = connection.transaction(
            isolation="repeatable_read",
            readonly=True,
        )
        await asyncio.wait_for(transaction.start(), timeout=client_timeout)
        transaction_started = True
        await asyncio.wait_for(
            connection.execute(
                "SELECT pg_catalog.set_config('statement_timeout', $1, true)",
                str(statement_timeout_ms),
            ),
            timeout=client_timeout,
        )
        try:
            snapshot = await asyncio.wait_for(
                capture_snapshot(connection),
                timeout=client_timeout,
            )
        except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            raise _PreApplyRevalidationCaptureFailure from None
        if not isinstance(snapshot, Mapping):
            raise PreApplyRevalidationContractError(
                "pre-apply revalidation snapshot capture is invalid"
            )
        try:
            snapshot_evidence = compare_live_preflight_snapshot(plan, snapshot)
        except LivePreflightContractError as err:
            raise PreApplyRevalidationContractError(str(err)) from None

        privilege_rows: list[dict[str, object]] = []
        for requirement, query in zip(
            manifest.privilege_requirements,
            privilege_queries,
            strict=True,
        ):
            allowed = await asyncio.wait_for(
                connection.fetchval(
                    query.sql,
                    *query.parameters,
                    timeout=client_timeout,
                ),
                timeout=client_timeout,
            )
            if not isinstance(allowed, bool):
                raise PreApplyRevalidationContractError(
                    "pre-apply revalidation privilege result is invalid"
                )
            privilege_rows.append(
                {
                    "statement_index": requirement.statement_index,
                    "privilege": requirement.privilege,
                    "scope": requirement.scope,
                    "schema_name": requirement.schema_name,
                    "table_name": requirement.table_name,
                    "allowed": allowed,
                }
            )

        precondition_rows: list[dict[str, object]] = []
        for precondition_query in manifest.precondition_queries:
            passed = await asyncio.wait_for(
                _fetch_pre_apply_precondition(
                    connection,
                    precondition_query,
                    client_timeout=client_timeout,
                ),
                timeout=client_timeout,
            )
            if not isinstance(passed, bool):
                raise PreApplyRevalidationContractError(
                    "pre-apply revalidation precondition result is invalid"
                )
            precondition_rows.append(
                {
                    "statement_index": precondition_query.statement_index,
                    "precondition_index": precondition_query.precondition_index,
                    "kind": precondition_query.kind,
                    "passed": passed,
                }
            )

        observed_base_digest = snapshot_evidence.get("observed_base_digest")
        observation: dict[str, object] = {
            "plan_digest": manifest.plan_digest,
            "observed_base_digest": observed_base_digest,
            "privileges": privilege_rows,
            "preconditions": precondition_rows,
        }
        assessment = assess_pre_apply_revalidation_observation(
            manifest,
            observation,
        )
        await asyncio.wait_for(transaction.commit(), timeout=client_timeout)
        return assessment
    except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
        if transaction_started and transaction is not None:
            try:
                await asyncio.wait_for(
                    transaction.rollback(),
                    timeout=client_timeout,
                )
            except Exception:
                # Best-effort cleanup must not mask cancellation or shutdown.
                pass
        raise
    except Exception as err:
        if transaction_started and transaction is not None:
            try:
                await asyncio.wait_for(
                    transaction.rollback(),
                    timeout=client_timeout,
                )
            except Exception:
                # Best-effort cleanup must not mask the original target failure.
                pass
        if isinstance(err, PreApplyRevalidationContractError):
            raise
        raise PreApplyRevalidationContractError(
            "pre-apply revalidation capture failed"
        ) from None


def assess_pre_apply_revalidation_observation(
    manifest: PreApplyRevalidationManifest,
    observation: Mapping[str, object],
) -> PreApplyRevalidationAssessment:
    """Validate complete positional evidence and derive non-authorizing facts.

    The caller remains responsible for proving that observations were captured
    freshly while holding the manifest locks on the intended target connection.
    This pure function cannot establish those facts or grant apply authority.
    """

    if not isinstance(manifest, PreApplyRevalidationManifest):
        raise PreApplyRevalidationContractError(
            "pre-apply revalidation manifest is invalid"
        )
    if not isinstance(observation, Mapping) or set(observation) != _OBSERVATION_FIELDS:
        raise PreApplyRevalidationContractError(
            "pre-apply revalidation observation contract is invalid"
        )
    plan_digest = _require_digest(
        observation.get("plan_digest"), name="observation plan digest"
    )
    if plan_digest != manifest.plan_digest:
        raise PreApplyRevalidationContractError(
            "pre-apply revalidation observation plan digest does not match"
        )
    observed_base_digest = _require_digest(
        observation.get("observed_base_digest"), name="observed base digest"
    )

    privilege_rows = observation.get("privileges")
    if not isinstance(privilege_rows, list) or len(privilege_rows) != len(
        manifest.privilege_requirements
    ):
        raise PreApplyRevalidationContractError(
            "pre-apply revalidation privilege observations are incomplete"
        )
    privilege_results: list[bool] = []
    for requirement, row in zip(
        manifest.privilege_requirements,
        privilege_rows,
        strict=True,
    ):
        if not isinstance(row, Mapping) or set(row) != _PRIVILEGE_OBSERVATION_FIELDS:
            raise PreApplyRevalidationContractError(
                "pre-apply revalidation privilege observation is invalid"
            )
        expected = {
            "statement_index": requirement.statement_index,
            "privilege": requirement.privilege,
            "scope": requirement.scope,
            "schema_name": requirement.schema_name,
            "table_name": requirement.table_name,
        }
        if any(row.get(field) != value for field, value in expected.items()):
            raise PreApplyRevalidationContractError(
                "pre-apply revalidation privilege observation does not match manifest"
            )
        allowed = row.get("allowed")
        if not isinstance(allowed, bool):
            raise PreApplyRevalidationContractError(
                "pre-apply revalidation privilege result is invalid"
            )
        privilege_results.append(allowed)

    precondition_rows = observation.get("preconditions")
    if not isinstance(precondition_rows, list) or len(precondition_rows) != len(
        manifest.precondition_queries
    ):
        raise PreApplyRevalidationContractError(
            "pre-apply revalidation precondition observations are incomplete"
        )
    precondition_results: list[bool] = []
    for query, row in zip(
        manifest.precondition_queries,
        precondition_rows,
        strict=True,
    ):
        if not isinstance(row, Mapping) or set(row) != _PRECONDITION_OBSERVATION_FIELDS:
            raise PreApplyRevalidationContractError(
                "pre-apply revalidation precondition observation is invalid"
            )
        expected = {
            "statement_index": query.statement_index,
            "precondition_index": query.precondition_index,
            "kind": query.kind,
        }
        if any(row.get(field) != value for field, value in expected.items()):
            raise PreApplyRevalidationContractError(
                "pre-apply revalidation precondition observation "
                "does not match manifest"
            )
        passed = row.get("passed")
        if not isinstance(passed, bool):
            raise PreApplyRevalidationContractError(
                "pre-apply revalidation precondition result is invalid"
            )
        precondition_results.append(passed)

    return PreApplyRevalidationAssessment(
        observed_base_digest=observed_base_digest,
        base_matches=observed_base_digest == manifest.base_digest,
        privileges_satisfied=all(privilege_results),
        preconditions_satisfied=all(precondition_results),
    )
