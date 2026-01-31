from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProjectMember


async def require_project_member(
    session: AsyncSession,
    project_space_uuid: uuid.UUID,
    user_account_uuid: uuid.UUID,
) -> str:
    row = await session.execute(
        select(ProjectMember.project_role).where(
            ProjectMember.project_space_uuid == project_space_uuid,
            ProjectMember.user_account_uuid == user_account_uuid,
        )
    )
    role = row.scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=403, detail="project access denied")
    return str(role)
