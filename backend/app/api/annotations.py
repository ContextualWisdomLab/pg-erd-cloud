from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.db import get_read_session, get_session
from app.models import TableAnnotation
from app.permissions import require_project_member
from app.schemas import TableAnnotationOut, TableAnnotationUpsertIn

router = APIRouter(prefix="/api/annotations", tags=["annotations"])


def _to_out(ann: TableAnnotation) -> TableAnnotationOut:
    return TableAnnotationOut(
        table_annotation_uuid=ann.table_annotation_uuid,
        schema_name=ann.schema_name,
        relation_name=ann.relation_name,
        body=ann.body,
        created_at=ann.created_at,
        updated_at=ann.updated_at,
    )


async def _get_authorized_annotation(
    session: AsyncSession,
    table_annotation_uuid: uuid.UUID,
    user: CurrentUser,
    minimum_role: str | None = None,
) -> TableAnnotation | None:
    """Fetch an annotation only after project membership has been checked.

    Returns ``None`` for both missing and unauthorized so callers can respond
    with a uniform 404 (no existence enumeration / IDOR).
    """
    project_space_uuid = await session.scalar(
        select(TableAnnotation.project_space_uuid).where(
            TableAnnotation.table_annotation_uuid == table_annotation_uuid
        )
    )
    if project_space_uuid is None:
        return None
    try:
        await require_project_member(
            session,
            project_space_uuid,
            user.user_account_uuid,
            minimum_role=minimum_role,
        )
    except HTTPException as exc:
        if exc.status_code == 403:
            return None
        raise
    return await session.get(TableAnnotation, table_annotation_uuid)


@router.get(
    "/by-project/{project_space_uuid}", response_model=list[TableAnnotationOut]
)
async def list_annotations(
    project_space_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> list[TableAnnotationOut]:
    """List table annotations for a project."""
    await require_project_member(session, project_space_uuid, user.user_account_uuid)
    rows = await session.execute(
        select(TableAnnotation)
        .where(TableAnnotation.project_space_uuid == project_space_uuid)
        .order_by(TableAnnotation.schema_name, TableAnnotation.relation_name)
    )
    return [_to_out(a) for a in rows.scalars().all()]


@router.put(
    "/by-project/{project_space_uuid}", response_model=TableAnnotationOut
)
async def upsert_annotation(
    project_space_uuid: uuid.UUID,
    body: TableAnnotationUpsertIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TableAnnotationOut:
    """Create or update the note for one table in a project (editor role).

    Keyed by (project, schema_name, relation_name); a unique constraint keeps
    it to a single note per table.
    """
    await require_project_member(
        session, project_space_uuid, user.user_account_uuid, minimum_role="editor"
    )
    now = dt.datetime.now(dt.timezone.utc)
    existing = await session.scalar(
        select(TableAnnotation).where(
            TableAnnotation.project_space_uuid == project_space_uuid,
            TableAnnotation.schema_name == body.schema_name,
            TableAnnotation.relation_name == body.relation_name,
        )
    )
    if existing is not None:
        existing.body = body.body
        existing.updated_at = now
        ann = existing
    else:
        ann = TableAnnotation(
            table_annotation_uuid=uuid.uuid4(),
            project_space_uuid=project_space_uuid,
            schema_name=body.schema_name,
            relation_name=body.relation_name,
            body=body.body,
            created_by=user.user_account_uuid,
            created_at=now,
            updated_at=now,
        )
        session.add(ann)
    await session.commit()
    return _to_out(ann)


@router.delete("/{table_annotation_uuid}")
async def delete_annotation(
    table_annotation_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    """Delete a table annotation (requires editor membership on its project)."""
    ann = await _get_authorized_annotation(
        session, table_annotation_uuid, user, minimum_role="editor"
    )
    if ann is None:
        raise HTTPException(status_code=404, detail="annotation not found")
    await session.delete(ann)
    await session.commit()
    return {"ok": True}
