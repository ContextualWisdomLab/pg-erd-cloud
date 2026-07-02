from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.db import get_read_session, get_session
from app.llm_quota import enforce_llm_draft_quota
from app.llm_usage import record_llm_draft_usage
from app.metrics import record_product_event
from app.models import (
    DbConnection,
    JobQueue,
    SchemaSnapshot,
    SchemaSnapshotData,
)
from app.permissions import require_project_member
from app.schemas import SnapshotCreateIn, SnapshotDetailOut, SnapshotOut
from app.ddl.export import snapshot_json_to_sql
from app.jobs.valkey_queue import enqueue_job_signal
from app.spec.llm import (
    LlmConfigurationError,
    LlmPromptTooLargeError,
    LlmProviderError,
    generate_index_design_llm_draft,
    generate_reversing_llm_draft,
)
from app.spec.index_design import generate_index_design_spec
from app.spec.reversing import generate_reversing_spec
from app.usage_quotas import enforce_snapshot_quota

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])


def _snapshot_not_found(schema_snapshot_uuid: uuid.UUID) -> SnapshotDetailOut:
    """Return the uniform snapshot-not-found response."""

    return SnapshotDetailOut(
        schema_snapshot_uuid=schema_snapshot_uuid,
        status="not_found",
        schema_filter=None,
        error_message="snapshot not found",
        snapshot_json=None,
    )


def _snapshot_project_space_uuid(snap: SchemaSnapshot) -> uuid.UUID | None:
    return getattr(snap, "project_space_uuid", None)


async def _get_authorized_snapshot(
    session: AsyncSession,
    schema_snapshot_uuid: uuid.UUID,
    user: CurrentUser,
) -> SchemaSnapshot | None:
    """Fetch a snapshot only after project membership has been checked."""

    project_space_uuid = await session.scalar(
        select(SchemaSnapshot.project_space_uuid).where(
            SchemaSnapshot.schema_snapshot_uuid == schema_snapshot_uuid
        )
    )
    if project_space_uuid is None:
        return None

    try:
        await require_project_member(
            session, project_space_uuid, user.user_account_uuid
        )
    except HTTPException as exc:
        if exc.status_code == 403:
            return None
        raise

    return await session.get(SchemaSnapshot, schema_snapshot_uuid)


async def _enforce_authenticated_llm_draft_quota(
    *,
    artifact: str,
    snapshot_json: dict,
    user: CurrentUser,
    snap: SchemaSnapshot,
    schema_snapshot_uuid: uuid.UUID,
) -> None:
    try:
        await enforce_llm_draft_quota(f"account:{user.user_account_uuid}")
    except HTTPException:
        record_llm_draft_usage(
            surface="authenticated",
            artifact=artifact,
            outcome="quota_exceeded",
            snapshot_json=snapshot_json,
            user_account_uuid=user.user_account_uuid,
            project_space_uuid=_snapshot_project_space_uuid(snap),
            schema_snapshot_uuid=schema_snapshot_uuid,
            error_code="quota_exceeded",
        )
        raise


@router.post("/by-project/{project_space_uuid}", response_model=SnapshotOut)
async def create_snapshot(
    project_space_uuid: uuid.UUID,
    body: SnapshotCreateIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SnapshotOut:
    """Create a schema snapshot job for a project connection."""
    try:
        await require_project_member(
            session, project_space_uuid, user.user_account_uuid, minimum_role="editor"
        )
    except HTTPException:
        record_product_event("snapshot", "create", "denied")
        raise

    # Ensure connection belongs to this project
    conn = await session.get(DbConnection, body.db_connection_uuid)
    if conn is None or conn.project_space_uuid != project_space_uuid:
        record_product_event("snapshot", "create", "not_found")
        raise HTTPException(status_code=404, detail="connection not found")
    try:
        await enforce_snapshot_quota(session, project_space_uuid)
    except HTTPException:
        record_product_event("snapshot", "create", "denied")
        raise

    snap = SchemaSnapshot(
        schema_snapshot_uuid=uuid.uuid4(),
        project_space_uuid=project_space_uuid,
        db_connection_uuid=body.db_connection_uuid,
        status="queued",
        schema_filter=body.schema_filter,
        started_at=None,
        finished_at=None,
        error_message=None,
        created_at=dt.datetime.now(dt.timezone.utc),
    )
    session.add(snap)

    job = JobQueue(
        job_queue_uuid=uuid.uuid4(),
        job_type="snapshot",
        status="queued",
        payload_json={"schema_snapshot_uuid": str(snap.schema_snapshot_uuid)},
        run_after=dt.datetime.now(dt.timezone.utc),
        attempt_count=0,
        last_error=None,
        created_at=dt.datetime.now(dt.timezone.utc),
        started_at=None,
        finished_at=None,
    )
    session.add(job)

    await session.commit()
    await enqueue_job_signal(job.job_queue_uuid, job.run_after)
    record_product_event("snapshot", "create", "queued")
    return SnapshotOut(
        schema_snapshot_uuid=snap.schema_snapshot_uuid,
        status=snap.status,
        schema_filter=snap.schema_filter,
    )


@router.get("/{schema_snapshot_uuid}", response_model=SnapshotDetailOut)
async def get_snapshot(
    schema_snapshot_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> SnapshotDetailOut:
    """Get a snapshot's status and (if present) captured JSON."""
    snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    if snap is None:
        return _snapshot_not_found(schema_snapshot_uuid)
    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    return SnapshotDetailOut(
        schema_snapshot_uuid=snap.schema_snapshot_uuid,
        status=snap.status,
        schema_filter=snap.schema_filter,
        error_message=snap.error_message,
        snapshot_json=data.snapshot_json if data else None,
    )


@router.get("/{schema_snapshot_uuid}/export.sql", response_class=PlainTextResponse)
async def export_snapshot_sql(
    schema_snapshot_uuid: uuid.UUID,
    dialect: str = Query("postgresql", pattern="^(postgresql|snowflake)$"),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> str:
    """Export a snapshot as dialect-specific SQL DDL (best-effort)."""
    snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    if snap is None:
        return "-- snapshot not found\n"
    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    if data is None:
        return "-- snapshot data not found\n"
    return snapshot_json_to_sql(data.snapshot_json, target_dialect=dialect)


@router.get(
    "/{schema_snapshot_uuid}/reversing-spec.md",
    response_class=PlainTextResponse,
)
async def export_snapshot_reversing_spec(
    schema_snapshot_uuid: uuid.UUID,
    mode: str = Query("markdown", pattern="^(markdown|llm-prompt|llm-draft)$"),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> str:
    """Export a snapshot as a DB reversing spec or LLM prompt."""
    snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    if snap is None:
        return "# DB Reversing Specification\n\nSnapshot not found.\n"
    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    if data is None:
        return "# DB Reversing Specification\n\nSnapshot data not found.\n"
    if mode == "llm-draft":
        await _enforce_authenticated_llm_draft_quota(
            artifact="reversing_spec",
            snapshot_json=data.snapshot_json,
            user=user,
            snap=snap,
            schema_snapshot_uuid=schema_snapshot_uuid,
        )
        try:
            draft = await generate_reversing_llm_draft(data.snapshot_json)
        except LlmConfigurationError as exc:
            record_llm_draft_usage(
                surface="authenticated",
                artifact="reversing_spec",
                outcome="configuration_error",
                snapshot_json=data.snapshot_json,
                user_account_uuid=user.user_account_uuid,
                project_space_uuid=_snapshot_project_space_uuid(snap),
                schema_snapshot_uuid=schema_snapshot_uuid,
                error_code="configuration_error",
            )
            raise HTTPException(
                status_code=503, detail="LLM configuration error"
            ) from exc
        except LlmPromptTooLargeError as exc:
            record_llm_draft_usage(
                surface="authenticated",
                artifact="reversing_spec",
                outcome="prompt_too_large",
                snapshot_json=data.snapshot_json,
                user_account_uuid=user.user_account_uuid,
                project_space_uuid=_snapshot_project_space_uuid(snap),
                schema_snapshot_uuid=schema_snapshot_uuid,
                error_code="prompt_too_large",
            )
            raise HTTPException(status_code=413, detail="LLM prompt too large") from exc
        except LlmProviderError as exc:
            record_llm_draft_usage(
                surface="authenticated",
                artifact="reversing_spec",
                outcome="provider_error",
                snapshot_json=data.snapshot_json,
                user_account_uuid=user.user_account_uuid,
                project_space_uuid=_snapshot_project_space_uuid(snap),
                schema_snapshot_uuid=schema_snapshot_uuid,
                error_code="provider_error",
            )
            raise HTTPException(
                status_code=502, detail="LLM provider request failed"
            ) from exc
        record_llm_draft_usage(
            surface="authenticated",
            artifact="reversing_spec",
            outcome="success",
            snapshot_json=data.snapshot_json,
            output_text=draft,
            user_account_uuid=user.user_account_uuid,
            project_space_uuid=_snapshot_project_space_uuid(snap),
            schema_snapshot_uuid=schema_snapshot_uuid,
        )
        return draft
    return generate_reversing_spec(data.snapshot_json, mode=mode)


@router.get(
    "/{schema_snapshot_uuid}/index-design.md",
    response_class=PlainTextResponse,
)
async def export_snapshot_index_design(
    schema_snapshot_uuid: uuid.UUID,
    mode: str = Query("markdown", pattern="^(markdown|llm-prompt|llm-draft)$"),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> str:
    """Export table/index design guidance or an LLM prompt."""
    snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    if snap is None:
        return "# ERD Index Design\n\nSnapshot not found.\n"
    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    if data is None:
        return "# ERD Index Design\n\nSnapshot data not found.\n"
    if mode == "llm-draft":
        await _enforce_authenticated_llm_draft_quota(
            artifact="index_design",
            snapshot_json=data.snapshot_json,
            user=user,
            snap=snap,
            schema_snapshot_uuid=schema_snapshot_uuid,
        )
        try:
            draft = await generate_index_design_llm_draft(data.snapshot_json)
        except LlmConfigurationError as exc:
            record_llm_draft_usage(
                surface="authenticated",
                artifact="index_design",
                outcome="configuration_error",
                snapshot_json=data.snapshot_json,
                user_account_uuid=user.user_account_uuid,
                project_space_uuid=_snapshot_project_space_uuid(snap),
                schema_snapshot_uuid=schema_snapshot_uuid,
                error_code="configuration_error",
            )
            raise HTTPException(
                status_code=503, detail="LLM configuration error"
            ) from exc
        except LlmPromptTooLargeError as exc:
            record_llm_draft_usage(
                surface="authenticated",
                artifact="index_design",
                outcome="prompt_too_large",
                snapshot_json=data.snapshot_json,
                user_account_uuid=user.user_account_uuid,
                project_space_uuid=_snapshot_project_space_uuid(snap),
                schema_snapshot_uuid=schema_snapshot_uuid,
                error_code="prompt_too_large",
            )
            raise HTTPException(status_code=413, detail="LLM prompt too large") from exc
        except LlmProviderError as exc:
            record_llm_draft_usage(
                surface="authenticated",
                artifact="index_design",
                outcome="provider_error",
                snapshot_json=data.snapshot_json,
                user_account_uuid=user.user_account_uuid,
                project_space_uuid=_snapshot_project_space_uuid(snap),
                schema_snapshot_uuid=schema_snapshot_uuid,
                error_code="provider_error",
            )
            raise HTTPException(
                status_code=502, detail="LLM provider request failed"
            ) from exc
        record_llm_draft_usage(
            surface="authenticated",
            artifact="index_design",
            outcome="success",
            snapshot_json=data.snapshot_json,
            output_text=draft,
            user_account_uuid=user.user_account_uuid,
            project_space_uuid=_snapshot_project_space_uuid(snap),
            schema_snapshot_uuid=schema_snapshot_uuid,
        )
        return draft
    return generate_index_design_spec(data.snapshot_json, mode=mode)


@router.get("/by-project/{project_space_uuid}", response_model=list[SnapshotOut])
async def list_snapshots(
    project_space_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> list[SnapshotOut]:
    """List snapshots for a project."""
    await require_project_member(session, project_space_uuid, user.user_account_uuid)
    rows = await session.execute(
        select(SchemaSnapshot)
        .where(SchemaSnapshot.project_space_uuid == project_space_uuid)
        .order_by(SchemaSnapshot.created_at.desc())
    )
    snaps = rows.scalars().all()
    return [
        SnapshotOut(
            schema_snapshot_uuid=s.schema_snapshot_uuid,
            status=s.status,
            schema_filter=s.schema_filter,
        )
        for s in snaps
    ]
