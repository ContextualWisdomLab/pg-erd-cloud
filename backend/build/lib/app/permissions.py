from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProjectMember

_ROLE_RANK = {"viewer": 0, "editor": 1, "owner": 2}


async def require_project_member(
    session: AsyncSession,
    project_space_uuid: uuid.UUID,
    user_account_uuid: uuid.UUID,
    minimum_role: str | None = None,
) -> str:
    """Ensure the user is a project member with the required role."""
    row = await session.execute(
        select(ProjectMember.project_role).where(
            ProjectMember.project_space_uuid == project_space_uuid,
            ProjectMember.user_account_uuid == user_account_uuid,
        )
    )
    role = row.scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=403, detail="project access denied")
    role_text = str(role)
    if minimum_role is not None:
        if _ROLE_RANK.get(role_text, -1) < _ROLE_RANK.get(minimum_role, 999):
            raise HTTPException(status_code=403, detail="insufficient project role")
    return role_text
