from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ProjectSpace
from app.schemas import ProjectCreateIn, ProjectOut
from app.sanitize import sanitize_for_storage


router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    session: AsyncSession = Depends(get_session),
) -> list[ProjectOut]:
    rows = await session.execute(
        select(ProjectSpace).order_by(ProjectSpace.created_at.desc())
    )
    projects = rows.scalars().all()
    return [
        ProjectOut(project_space_uuid=p.project_space_uuid, project_name=p.project_name)
        for p in projects
    ]


@router.post("", response_model=ProjectOut)
async def create_project(
    body: ProjectCreateIn, session: AsyncSession = Depends(get_session)
) -> ProjectOut:
    # MVP: no auth yet; created_by is random placeholder.
    created_by = uuid.uuid4()
    p = ProjectSpace(
        project_space_uuid=uuid.uuid4(),
        project_name=str(sanitize_for_storage(body.project_name)),
        created_by_user_uuid=created_by,
        created_at=dt.datetime.now(dt.timezone.utc),
    )
    session.add(p)
    await session.commit()
    return ProjectOut(
        project_space_uuid=p.project_space_uuid, project_name=p.project_name
    )
