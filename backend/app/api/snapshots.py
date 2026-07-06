from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.db import get_read_session, get_session
from app.models import (
    DbConnection,
    JobQueue,
    SchemaSnapshot,
    SchemaSnapshotData,
)
from app.permissions import require_project_member
from app.schemas import (
    AuditColumnsOut,
    NamingLintOut,
    SnapshotCreateIn,
    SnapshotDetailOut,
    SnapshotOut,
    WideTablesOut,
)
from app.ddl.export import snapshot_json_to_sql
from app.spec.audit_columns import check_audit_columns
from app.spec.naming_lint import lint_naming
from app.spec.wide_tables import detect_wide_tables
from app.jobs.valkey_queue import enqueue_job_signal
from app.spec.llm import (
    LlmConfigurationError,
    LlmProviderError,
    generate_index_design_llm_draft,
    generate_reversing_llm_draft,
)
from app.spec.index_design import generate_index_design_spec
from app.spec.reversing import generate_reversing_spec

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


@router.post("/by-project/{project_space_uuid}", response_model=SnapshotOut)
async def create_snapshot(
    project_space_uuid: uuid.UUID,
    body: SnapshotCreateIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SnapshotOut:
    """Create a schema snapshot job for a project connection."""
    await require_project_member(
        session, project_space_uuid, user.user_account_uuid, minimum_role="editor"
    )

    # Ensure connection belongs to this project
    conn = await session.get(DbConnection, body.db_connection_uuid)
    if conn is None or conn.project_space_uuid != project_space_uuid:
        raise HTTPException(status_code=404, detail="connection not found")

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


@router.get("/{schema_snapshot_uuid}/wide-tables", response_model=WideTablesOut)
async def wide_tables(
    schema_snapshot_uuid: uuid.UUID,
    warn_threshold: int = Query(40, ge=1, le=1600),
    info_threshold: int = Query(25, ge=1, le=1600),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> WideTablesOut:
    """Flag wide / denormalized tables by column count (configurable thresholds).

    IDOR-safe (uniform not-found for missing/unauthorized snapshots).
    """
    snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    if snap is None:
        return WideTablesOut(
            schema_snapshot_uuid=schema_snapshot_uuid, status="not_found", report=None
        )
    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    report = detect_wide_tables(
        data.snapshot_json if data else None,
        warn_threshold=warn_threshold,
        info_threshold=info_threshold,
    )
    return WideTablesOut(
        schema_snapshot_uuid=schema_snapshot_uuid, status="ok", report=report
    )


@router.get("/{schema_snapshot_uuid}/audit-columns", response_model=AuditColumnsOut)
async def audit_columns(
    schema_snapshot_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> AuditColumnsOut:
    """Flag tables missing created_at/updated_at when the schema's own
    majority follows that convention (no external style imposed).

    IDOR-safe (uniform not-found for missing/unauthorized snapshots).
    """
    snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    if snap is None:
        return AuditColumnsOut(
            schema_snapshot_uuid=schema_snapshot_uuid, status="not_found", report=None
        )
    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    report = check_audit_columns(data.snapshot_json if data else None)
    return AuditColumnsOut(
        schema_snapshot_uuid=schema_snapshot_uuid, status="ok", report=report
    )


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
        try:
            return await generate_reversing_llm_draft(data.snapshot_json)
        except LlmConfigurationError as exc:
            raise HTTPException(
                status_code=503, detail="LLM configuration error"
            ) from exc
        except LlmProviderError as exc:
            raise HTTPException(
                status_code=502, detail="LLM provider request failed"
            ) from exc
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
        try:
            return await generate_index_design_llm_draft(data.snapshot_json)
        except LlmConfigurationError as exc:
            raise HTTPException(
                status_code=503, detail="LLM configuration error"
            ) from exc
        except LlmProviderError as exc:
            raise HTTPException(
                status_code=502, detail="LLM provider request failed"
            ) from exc
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


@router.get("/{schema_snapshot_uuid}/naming-lint", response_model=NamingLintOut)
async def naming_lint(
    schema_snapshot_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> NamingLintOut:
    """Lint identifier names: reserved words and quoting-required names (breaking),
    discouraged keywords, and case inconsistency vs the schema's own dominant style.

    IDOR-safe (uniform not-found for missing/unauthorized snapshots).
    """
    snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    if snap is None:
        return NamingLintOut(
            schema_snapshot_uuid=schema_snapshot_uuid, status="not_found", report=None
        )
    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    report = lint_naming(data.snapshot_json if data else None)
    return NamingLintOut(
        schema_snapshot_uuid=schema_snapshot_uuid, status="ok", report=report
    )
