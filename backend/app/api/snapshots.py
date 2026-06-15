from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends
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
from app.schemas import SnapshotCreateIn, SnapshotDetailOut, SnapshotOut
from app.ddl.export import snapshot_json_to_sql

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])


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
        return SnapshotOut(
            schema_snapshot_uuid=uuid.uuid4(),
            status="failed",
            schema_filter=body.schema_filter,
        )

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
    snap = await session.get(SchemaSnapshot, schema_snapshot_uuid)
    if snap is None:
        return SnapshotDetailOut(
            schema_snapshot_uuid=schema_snapshot_uuid,
            status="not_found",
            schema_filter=None,
            error_message="snapshot not found",
            snapshot_json=None,
        )
    await require_project_member(
        session, snap.project_space_uuid, user.user_account_uuid
    )
    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    return SnapshotDetailOut(
        schema_snapshot_uuid=snap.schema_snapshot_uuid,
        status=snap.status,
        schema_filter=snap.schema_filter,
        error_message=snap.error_message,
        snapshot_json=data.snapshot_json if data else None,
    )


@router.get(
    "/{schema_snapshot_uuid}/export.sql", response_class=PlainTextResponse
)
async def export_snapshot_sql(
    schema_snapshot_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> str:
    """Export a snapshot as PostgreSQL DDL (best-effort)."""
    snap = await session.get(SchemaSnapshot, schema_snapshot_uuid)
    if snap is None:
        return "-- snapshot not found\n"
    await require_project_member(
        session, snap.project_space_uuid, user.user_account_uuid
    )
    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    if data is None:
        return "-- snapshot data not found\n"
    return snapshot_json_to_sql(data.snapshot_json)


@router.get(
    "/by-project/{project_space_uuid}", response_model=list[SnapshotOut]
)
async def list_snapshots(
    project_space_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> list[SnapshotOut]:
    """List snapshots for a project."""
    await require_project_member(
        session, project_space_uuid, user.user_account_uuid
    )
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
