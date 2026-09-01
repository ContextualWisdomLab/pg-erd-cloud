from __future__ import annotations

import datetime as dt
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.db import get_read_session, get_session
from app.models import DiagramView
from app.permissions import require_project_member
from app.schemas import (
    DiagramViewCreateIn,
    DiagramViewDetailOut,
    DiagramViewOut,
)

router = APIRouter(prefix="/api/diagram-views", tags=["diagram-views"])

# Saved layouts are small (positions for a few hundred tables). Bound the
# serialized payload so a client cannot store arbitrarily large blobs.
MAX_LAYOUT_BYTES = 512 * 1024


def _bound_layout_size(layout_payload: dict) -> None:
    encoded_layout = json.dumps(layout_payload, separators=(",", ":")).encode("utf-8")
    if len(encoded_layout) > MAX_LAYOUT_BYTES:
        raise HTTPException(status_code=413, detail="layout payload too large")


async def _get_authorized_view(
    database_session: AsyncSession,
    diagram_view_uuid: uuid.UUID,
    current_user: CurrentUser,
    minimum_role: str | None = None,
) -> DiagramView | None:
    """Fetch a view only after project membership has been checked.

    Returns ``None`` for both missing and unauthorized so callers can respond
    with a uniform 404 (no existence enumeration).
    """

    project_space_uuid = await database_session.scalar(
        select(DiagramView.project_space_uuid).where(
            DiagramView.diagram_view_uuid == diagram_view_uuid
        )
    )
    if project_space_uuid is None:
        return None
    try:
        await require_project_member(
            database_session,
            project_space_uuid,
            current_user.user_account_uuid,
            minimum_role=minimum_role,
        )
    except HTTPException as http_exception:
        if http_exception.status_code == 403:
            return None
        raise
    return await database_session.get(DiagramView, diagram_view_uuid)


@router.post("/by-project/{project_space_uuid}", response_model=DiagramViewOut)
async def create_view(
    project_space_uuid: uuid.UUID,
    diagram_view_request: DiagramViewCreateIn,
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_session),
) -> DiagramViewOut:
    """Save a new ERD canvas view for a project."""
    await require_project_member(
        database_session,
        project_space_uuid,
        current_user.user_account_uuid,
        minimum_role="editor",
    )
    _bound_layout_size(diagram_view_request.layout_json)
    current_time = dt.datetime.now(dt.timezone.utc)
    diagram_view = DiagramView(
        diagram_view_uuid=uuid.uuid4(),
        project_space_uuid=project_space_uuid,
        diagram_name=diagram_view_request.diagram_name,
        layout_json=diagram_view_request.layout_json,
        created_by=current_user.user_account_uuid,
        created_at=current_time,
        updated_at=current_time,
    )
    database_session.add(diagram_view)
    await database_session.commit()
    return DiagramViewOut(
        diagram_view_uuid=diagram_view.diagram_view_uuid,
        diagram_name=diagram_view.diagram_name,
        created_at=diagram_view.created_at,
        updated_at=diagram_view.updated_at,
    )


@router.get("/by-project/{project_space_uuid}", response_model=list[DiagramViewOut])
async def list_views(
    project_space_uuid: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_read_session),
) -> list[DiagramViewOut]:
    """List saved views for a project (newest first)."""
    await require_project_member(
        database_session,
        project_space_uuid,
        current_user.user_account_uuid,
    )
    query_result = await database_session.execute(
        select(DiagramView)
        .where(DiagramView.project_space_uuid == project_space_uuid)
        .order_by(DiagramView.updated_at.desc())
    )
    return [
        DiagramViewOut(
            diagram_view_uuid=diagram_view.diagram_view_uuid,
            diagram_name=diagram_view.diagram_name,
            created_at=diagram_view.created_at,
            updated_at=diagram_view.updated_at,
        )
        for diagram_view in query_result.scalars().all()
    ]


@router.get("/{diagram_view_uuid}", response_model=DiagramViewDetailOut)
async def get_view(
    diagram_view_uuid: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_read_session),
) -> DiagramViewDetailOut:
    """Get one saved view including its layout payload."""
    diagram_view = await _get_authorized_view(
        database_session,
        diagram_view_uuid,
        current_user,
    )
    if diagram_view is None:
        raise HTTPException(status_code=404, detail="diagram view not found")
    return DiagramViewDetailOut(
        diagram_view_uuid=diagram_view.diagram_view_uuid,
        diagram_name=diagram_view.diagram_name,
        layout_json=diagram_view.layout_json,
        created_at=diagram_view.created_at,
        updated_at=diagram_view.updated_at,
    )


@router.delete("/{diagram_view_uuid}")
async def delete_view(
    diagram_view_uuid: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    database_session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    """Delete a saved view (requires editor membership on its project)."""
    diagram_view = await _get_authorized_view(
        database_session,
        diagram_view_uuid,
        current_user,
        minimum_role="editor",
    )
    if diagram_view is None:
        raise HTTPException(status_code=404, detail="diagram view not found")
    await database_session.delete(diagram_view)
    await database_session.commit()
    return {"ok": True}
