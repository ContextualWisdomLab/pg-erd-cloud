"""Create immutable migration plans from stored model revisions."""

from __future__ import annotations

import datetime as dt
import json
import uuid
from collections.abc import Mapping
from typing import Any, cast

import anyio
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.db import get_session
from app.forward.migration_plan import compile_migration_plan
from app.forward.schema_model import SchemaModelValidationError
from app.forward.snapshot_adapter import snapshot_to_schema_model
from app.models import (
    DbConnection,
    MigrationPlan,
    SchemaModel,
    SchemaModelRevision,
    SchemaSnapshot,
    SchemaSnapshotData,
)
from app.permissions import require_project_member
from app.schemas import MigrationPlanCreateIn, MigrationPlanOut

router = APIRouter(prefix="/api/schema-model-revisions", tags=["migration-plans"])
PLAN_LIFETIME = dt.timedelta(hours=24)
MAX_PLAN_STATEMENTS = 1_000
MAX_PLAN_BYTES = 4 * 1024 * 1024


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
    return MigrationPlanOut(
        migration_plan_uuid=plan.migration_plan_uuid,
        plan_digest=plan.statement_digest,
        base_digest=plan.base_digest,
        target_digest=plan.target_digest,
        compiler_version=plan.compiler_version,
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
    "/{schema_model_revision_uuid}/migration-plans",
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
