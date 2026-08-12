"""Create immutable migration plans from stored model revisions."""

from __future__ import annotations

import datetime as dt
import json
import uuid
from collections.abc import Mapping
from typing import Annotated, Any, cast

import anyio
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import delete, exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.db import get_session
from app.forward.migration_plan import (
    compile_migration_plan,
    verify_migration_plan_digest,
)
from app.forward.migration_run import MigrationRunContractError, create_migration_run
from app.forward.schema_model import SchemaModelValidationError
from app.forward.snapshot_adapter import snapshot_to_schema_model
from app.models import (
    DbConnection,
    MigrationPlan,
    MigrationRun,
    SchemaModel,
    SchemaModelRevision,
    SchemaSnapshot,
    SchemaSnapshotData,
)
from app.permissions import require_project_member
from app.schemas import (
    MigrationApplyRunCreateIn,
    MigrationPlanCreateIn,
    MigrationPlanOut,
    MigrationRunActionOut,
    MigrationRunCreateIn,
    MigrationRunState,
)

router = APIRouter(prefix="/api", tags=["migration-plans"])
PLAN_LIFETIME = dt.timedelta(hours=24)
EXPIRED_PLAN_RETENTION = dt.timedelta(days=30)
MAX_PLAN_STATEMENTS = 1_000
MAX_PLAN_BYTES = 4 * 1024 * 1024


def _request_id(request: Request) -> str:
    """Return the middleware-selected request ID or a safe local fallback."""

    value = getattr(request.state, "request_id", None)
    if isinstance(value, str) and 1 <= len(value) <= 64:
        return value
    return str(uuid.uuid4())


def _creation_error(
    request: Request, *, status_code: int, code: str, detail: str
) -> HTTPException:
    """Return the stable sanitized error envelope for run creation."""

    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "detail": detail,
            "correlation_id": _request_id(request),
        },
    )


def _creation_contract_error(
    request: Request, error: MigrationRunContractError
) -> HTTPException:
    """Map internal creation failures onto bounded public error codes."""

    status_code, code = {
        "migration plan integrity verification failed": (
            status.HTTP_409_CONFLICT,
            "plan_integrity_invalid",
        ),
        "migration plan expired": (status.HTTP_409_CONFLICT, "plan_expired"),
        "migration plan cannot be dry-run": (
            status.HTTP_409_CONFLICT,
            "plan_not_dry_runnable",
        ),
        "idempotency key conflict": (
            status.HTTP_409_CONFLICT,
            "idempotency_key_conflict",
        ),
        "idempotency winner is unavailable": (
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "run_creation_unavailable",
        ),
        "idempotency key length is invalid": (
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "idempotency_key_invalid",
        ),
        "idempotency key contains a control character": (
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "idempotency_key_invalid",
        ),
    }.get(str(error), (status.HTTP_409_CONFLICT, "run_action_rejected"))
    return _creation_error(
        request,
        status_code=status_code,
        code=code,
        detail="dry-run creation was rejected",
    )


def _apply_creation_contract_error(
    request: Request, error: MigrationRunContractError
) -> HTTPException:
    """Map apply-intent rejection onto stable non-executing API errors."""

    status_code, code = {
        "migration plan integrity verification failed": (409, "plan_integrity_invalid"),
        "migration plan expired": (409, "plan_expired"),
        "migration plan cannot be dry-run": (409, "plan_not_executable"),
        "migration model revision is stale": (409, "stale_revision"),
        "passed dry run is invalid": (409, "passed_dry_run_invalid"),
        "target connection confirmation mismatch": (409, "target_confirmation_mismatch"),
        "destructive confirmation mismatch": (409, "destructive_confirmation_mismatch"),
        "apply confirmation is invalid": (422, "apply_confirmation_invalid"),
        "apply evidence is invalid": (422, "apply_confirmation_invalid"),
        "idempotency key conflict": (409, "idempotency_key_conflict"),
        "idempotency winner is unavailable": (503, "run_creation_unavailable"),
        "idempotency key length is invalid": (422, "idempotency_key_invalid"),
        "idempotency key contains a control character": (
            422,
            "idempotency_key_invalid",
        ),
    }.get(str(error), (409, "run_action_rejected"))
    return _creation_error(
        request,
        status_code=status_code,
        code=code,
        detail="apply intent creation was rejected",
    )


def _compile_and_serialize_plan(
    snapshot_json: Mapping[str, Any], model_json: Mapping[str, Any]
) -> tuple[dict[str, Any], bytes]:
    """Compile and serialize a plan outside the request event loop."""

    base_model = snapshot_to_schema_model(snapshot_json)
    plan_json = compile_migration_plan(base_model, model_json)
    serialized_plan = json.dumps(
        plan_json, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return plan_json, serialized_plan


def _plan_out(plan: MigrationPlan) -> MigrationPlanOut:
    """Return the public representation of one persisted immutable plan."""

    plan_json = plan.plan_json
    if (
        not verify_migration_plan_digest(plan_json, plan.statement_digest)
        or plan_json.get("compiler_version") != plan.compiler_version
        or plan_json.get("base_digest") != plan.base_digest
        or plan_json.get("target_digest") != plan.target_digest
    ):
        raise HTTPException(
            status_code=409,
            detail="migration plan integrity verification failed",
        )
    return MigrationPlanOut(
        migration_plan_uuid=plan.migration_plan_uuid,
        project_space_uuid=plan.project_space_uuid,
        schema_model_revision_uuid=plan.schema_model_revision_uuid,
        db_connection_uuid=plan.db_connection_uuid,
        base_schema_snapshot_uuid=plan.base_schema_snapshot_uuid,
        plan_digest=plan.statement_digest,
        base_digest=plan.base_digest,
        target_digest=plan.target_digest,
        compiler_version=plan.compiler_version,
        snapshot_contract_version=plan_json["snapshot_contract_version"],
        postgresql_major=plan_json["postgresql_major"],
        created_by_user_uuid=plan.created_by_user_uuid,
        created_at=plan.created_at,
        can_dry_run=bool(plan_json["can_dry_run"]),
        requires_destructive_confirmation=bool(
            plan_json["requires_destructive_confirmation"]
        ),
        statements=plan_json["statements"],
        proposed_statements=plan_json.get("proposed_statements", []),
        blockers=plan_json["blockers"],
        risk_summary=plan_json["risk_summary"],
        expires_at=plan.expires_at,
    )


async def _existing_plan(
    session: AsyncSession,
    *,
    revision_uuid: uuid.UUID,
    connection_uuid: uuid.UUID,
    snapshot_uuid: uuid.UUID,
    statement_digest: str,
) -> MigrationPlan | None:
    """Load the one plan allowed for an immutable compiler input identity."""

    return cast(
        MigrationPlan | None,
        await session.scalar(
            select(MigrationPlan).where(
                MigrationPlan.schema_model_revision_uuid == revision_uuid,
                MigrationPlan.db_connection_uuid == connection_uuid,
                MigrationPlan.base_schema_snapshot_uuid == snapshot_uuid,
                MigrationPlan.statement_digest == statement_digest,
            )
        ),
    )


async def _cleanup_expired_unreferenced_plans(
    session: AsyncSession,
    *,
    project_space_uuid: uuid.UUID,
    now: dt.datetime,
) -> int:
    """Delete old derived plans only when no durable run references them.

    Cleanup is tenant-scoped and retains every plan for 30 days after expiry.
    Run evidence uses a restrictive foreign key, and the correlated exclusion
    makes that retention boundary explicit before the database enforces it.
    """

    run_exists = exists(
        select(MigrationRun.migration_run_uuid).where(
            MigrationRun.migration_plan_uuid
            == MigrationPlan.migration_plan_uuid
        )
    )
    result = cast(
        Any,
        await session.execute(
            delete(MigrationPlan).where(
                MigrationPlan.project_space_uuid == project_space_uuid,
                MigrationPlan.expires_at <= now - EXPIRED_PLAN_RETENTION,
                ~run_exists,
            )
        ),
    )
    deleted = int(result.rowcount or 0)
    if deleted:
        await session.commit()
    return deleted


async def _load_plan_inputs(
    session: AsyncSession,
    schema_model_revision_uuid: uuid.UUID,
    body: MigrationPlanCreateIn,
) -> tuple[
    SchemaModel,
    SchemaModelRevision,
    DbConnection,
    SchemaSnapshot,
    SchemaSnapshotData,
] | None:
    revision = await session.get(SchemaModelRevision, schema_model_revision_uuid)
    if revision is None:
        return None
    model = await session.get(SchemaModel, revision.schema_model_uuid)
    connection = await session.get(DbConnection, body.db_connection_uuid)
    snapshot = await session.get(SchemaSnapshot, body.base_schema_snapshot_uuid)
    snapshot_data = await session.get(
        SchemaSnapshotData, body.base_schema_snapshot_uuid
    )
    if any(value is None for value in (model, connection, snapshot, snapshot_data)):
        return None
    return model, revision, connection, snapshot, snapshot_data  # type: ignore[return-value]


@router.post(
    "/migration-plans/{migration_plan_uuid}/dry-runs",
    response_model=MigrationRunActionOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_dry_run(
    migration_plan_uuid: uuid.UUID,
    body: MigrationRunCreateIn,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=255,
            pattern=r"^[^\x00-\x1F\x7F]+$",
        ),
    ],
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MigrationRunActionOut:
    """Persist an editor-authorized dry-run intent without executing SQL."""

    plan = await session.get(MigrationPlan, migration_plan_uuid)
    if plan is None:
        raise _creation_error(
            request,
            status_code=status.HTTP_404_NOT_FOUND,
            code="migration_plan_not_found",
            detail="migration plan not found",
        )
    try:
        await require_project_member(
            session,
            plan.project_space_uuid,
            user.user_account_uuid,
            minimum_role="editor",
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_403_FORBIDDEN:
            if exc.detail == "insufficient project role":
                raise _creation_error(
                    request,
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="run_role_required",
                    detail="editor role required",
                ) from exc
            raise _creation_error(
                request,
                status_code=status.HTTP_404_NOT_FOUND,
                code="migration_plan_not_found",
                detail="migration plan not found",
            ) from exc
        raise

    if body.plan_digest != plan.statement_digest:
        raise _creation_error(
            request,
            status_code=status.HTTP_409_CONFLICT,
            code="stale_plan",
            detail="migration plan digest does not match",
        )

    correlation_id = _request_id(request)
    try:
        creation = await create_migration_run(
            session,
            plan=plan,
            run_kind="dry_run",
            idempotency_key=idempotency_key,
            requested_by_user_uuid=user.user_account_uuid,
            evidence={"request_id": correlation_id, "request_source": "api"},
        )
    except MigrationRunContractError as exc:
        raise _creation_contract_error(request, exc) from exc
    await session.commit()
    return MigrationRunActionOut(
        migration_run_uuid=creation.migration_run_uuid,
        state=cast(MigrationRunState, creation.state),
        state_version=creation.state_version,
        cancellation_requested=creation.cancellation_requested,
        reused=creation.reused,
    )


@router.post(
    "/migration-plans/{migration_plan_uuid}/apply-runs",
    response_model=MigrationRunActionOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_apply_run(
    migration_plan_uuid: uuid.UUID,
    body: MigrationApplyRunCreateIn,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=255,
            pattern=r"^[^\x00-\x1F\x7F]+$",
        ),
    ],
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MigrationRunActionOut:
    """Persist deployer-reviewed apply intent without dispatch or execution."""

    plan = await session.get(MigrationPlan, migration_plan_uuid)
    if plan is None:
        raise _creation_error(
            request,
            status_code=404,
            code="migration_plan_not_found",
            detail="migration plan not found",
        )
    try:
        await require_project_member(
            session,
            plan.project_space_uuid,
            user.user_account_uuid,
            minimum_role="deployer",
        )
    except HTTPException as exc:
        if exc.status_code == 403:
            if exc.detail == "insufficient project role":
                raise _creation_error(
                    request,
                    status_code=403,
                    code="run_role_required",
                    detail="deployer role required",
                ) from exc
            raise _creation_error(
                request,
                status_code=404,
                code="migration_plan_not_found",
                detail="migration plan not found",
            ) from exc
        raise
    if body.plan_digest != plan.statement_digest:
        raise _creation_error(
            request,
            status_code=409,
            code="stale_plan",
            detail="migration plan digest does not match",
        )

    model_revision = await session.get(
        SchemaModelRevision, plan.schema_model_revision_uuid
    )
    if model_revision is None:
        raise _creation_error(
            request,
            status_code=409,
            code="stale_revision",
            detail="migration model revision is stale",
        )
    schema_model = await session.get(
        SchemaModel, model_revision.schema_model_uuid, with_for_update=True
    )
    if schema_model is None:
        raise _creation_error(
            request,
            status_code=409,
            code="stale_revision",
            detail="migration model revision is stale",
        )
    passed_dry_run = await session.get(MigrationRun, body.passed_dry_run_uuid)
    connection = await session.get(DbConnection, plan.db_connection_uuid)
    if passed_dry_run is None:
        raise _creation_error(
            request,
            status_code=409,
            code="passed_dry_run_invalid",
            detail="passed dry run is invalid",
        )
    if connection is None:
        raise _creation_error(
            request,
            status_code=409,
            code="target_confirmation_mismatch",
            detail="target connection confirmation does not match",
        )
    correlation_id = _request_id(request)
    try:
        creation = await create_migration_run(
            session,
            plan=plan,
            run_kind="apply",
            idempotency_key=idempotency_key,
            requested_by_user_uuid=user.user_account_uuid,
            evidence={"request_id": correlation_id, "request_source": "api"},
            passed_dry_run=passed_dry_run,
            connection=connection,
            typed_connection_name=body.target_connection_name,
            destructive_acknowledged=body.destructive_acknowledged,
            model_revision=model_revision,
            schema_model=schema_model,
        )
    except MigrationRunContractError as exc:
        raise _apply_creation_contract_error(request, exc) from exc
    await session.commit()
    return MigrationRunActionOut(
        migration_run_uuid=creation.migration_run_uuid,
        state=cast(MigrationRunState, creation.state),
        state_version=creation.state_version,
        cancellation_requested=creation.cancellation_requested,
        reused=creation.reused,
    )


@router.get(
    "/migration-plans/{migration_plan_uuid}",
    response_model=MigrationPlanOut,
)
async def get_migration_plan(
    migration_plan_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MigrationPlanOut:
    """Return one immutable plan preview to an authorized project member."""

    plan = await session.get(MigrationPlan, migration_plan_uuid)
    if plan is None:
        raise HTTPException(status_code=404, detail="migration plan not found")
    try:
        await require_project_member(
            session,
            plan.project_space_uuid,
            user.user_account_uuid,
        )
    except HTTPException as exc:
        if exc.status_code == 403:
            raise HTTPException(
                status_code=404, detail="migration plan not found"
            ) from exc
        raise
    return _plan_out(plan)


@router.post(
    "/schema-model-revisions/{schema_model_revision_uuid}/migration-plans",
    response_model=MigrationPlanOut,
)
async def create_migration_plan(
    schema_model_revision_uuid: uuid.UUID,
    body: MigrationPlanCreateIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MigrationPlanOut:
    """Compile and persist an exact, expiring, reviewable migration plan."""

    loaded = await _load_plan_inputs(session, schema_model_revision_uuid, body)
    if loaded is None:
        raise HTTPException(status_code=404, detail="migration plan input not found")
    model, revision, connection, snapshot, snapshot_data = loaded
    try:
        await require_project_member(
            session,
            model.project_space_uuid,
            user.user_account_uuid,
            minimum_role="editor",
        )
    except HTTPException as exc:
        if exc.status_code == 403:
            raise HTTPException(
                status_code=404, detail="migration plan input not found"
            ) from exc
        raise
    if not (
        connection.project_space_uuid
        == snapshot.project_space_uuid
        == model.project_space_uuid
    ):
        raise HTTPException(
            status_code=404,
            detail="migration plan input not found",
        )
    if snapshot.db_connection_uuid != connection.db_connection_uuid:
        raise HTTPException(
            status_code=422,
            detail="base snapshot was not captured from the target connection",
        )
    if snapshot.status != "succeeded":
        raise HTTPException(status_code=422, detail="base snapshot is not usable")
    if revision.schema_model_uuid != model.schema_model_uuid:
        raise HTTPException(status_code=422, detail="model revision binding is invalid")
    try:
        plan_json, serialized_plan = await anyio.to_thread.run_sync(
            _compile_and_serialize_plan,
            snapshot_data.snapshot_json,
            revision.model_json,
        )
    except SchemaModelValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    proposed_statements = plan_json.get("proposed_statements", [])
    if (
        len(plan_json["statements"]) + len(proposed_statements)
        > MAX_PLAN_STATEMENTS
        or len(serialized_plan) > MAX_PLAN_BYTES
    ):
        raise HTTPException(status_code=413, detail="migration plan is too large")

    now = dt.datetime.now(dt.timezone.utc)
    expires_at = now + PLAN_LIFETIME
    await _cleanup_expired_unreferenced_plans(
        session,
        project_space_uuid=model.project_space_uuid,
        now=now,
    )
    existing = await _existing_plan(
        session,
        revision_uuid=revision.schema_model_revision_uuid,
        connection_uuid=connection.db_connection_uuid,
        snapshot_uuid=snapshot.schema_snapshot_uuid,
        statement_digest=plan_json["plan_digest"],
    )
    if existing is not None:
        if existing.expires_at <= now:
            raise HTTPException(
                status_code=409,
                detail="matching migration plan expired; capture a fresh target snapshot",
            )
        return _plan_out(existing)
    plan = MigrationPlan(
        migration_plan_uuid=uuid.uuid4(),
        project_space_uuid=model.project_space_uuid,
        schema_model_revision_uuid=revision.schema_model_revision_uuid,
        db_connection_uuid=connection.db_connection_uuid,
        base_schema_snapshot_uuid=snapshot.schema_snapshot_uuid,
        compiler_version=plan_json["compiler_version"],
        base_digest=plan_json["base_digest"],
        target_digest=plan_json["target_digest"],
        statement_digest=plan_json["plan_digest"],
        plan_json=plan_json,
        created_by_user_uuid=user.user_account_uuid,
        expires_at=expires_at,
        created_at=now,
    )
    session.add(plan)
    try:
        await session.flush()
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        winner = await _existing_plan(
            session,
            revision_uuid=revision.schema_model_revision_uuid,
            connection_uuid=connection.db_connection_uuid,
            snapshot_uuid=snapshot.schema_snapshot_uuid,
            statement_digest=plan_json["plan_digest"],
        )
        if winner is None:
            raise
        if winner.expires_at <= now:
            raise HTTPException(
                status_code=409,
                detail="matching migration plan expired; capture a fresh target snapshot",
            ) from exc
        return _plan_out(winner)
    return _plan_out(plan)
