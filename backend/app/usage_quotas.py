from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DbConnection, ProjectSpace, SchemaSnapshot, ShareLink
from app.settings import settings


async def _scalar_count(session: AsyncSession, stmt: Any) -> int:
    result = await session.execute(stmt)
    value = result.scalar_one()
    return int(value or 0)


def _raise_quota_exceeded(resource_name: str) -> None:
    raise HTTPException(status_code=403, detail=f"{resource_name} quota exceeded")


async def enforce_project_quota(
    session: AsyncSession,
    user_account_uuid: uuid.UUID,
) -> None:
    limit = settings.billing_max_projects_per_user
    if limit <= 0:
        return

    current_count = await _scalar_count(
        session,
        select(func.count()).select_from(ProjectSpace).where(
            ProjectSpace.created_by_user_uuid == user_account_uuid
        ),
    )
    if current_count >= limit:
        _raise_quota_exceeded("project")


async def enforce_connection_quota(
    session: AsyncSession,
    project_space_uuid: uuid.UUID,
) -> None:
    limit = settings.billing_max_connections_per_project
    if limit <= 0:
        return

    current_count = await _scalar_count(
        session,
        select(func.count()).select_from(DbConnection).where(
            DbConnection.project_space_uuid == project_space_uuid
        ),
    )
    if current_count >= limit:
        _raise_quota_exceeded("connection")


async def enforce_snapshot_quota(
    session: AsyncSession,
    project_space_uuid: uuid.UUID,
) -> None:
    limit = settings.billing_max_snapshots_per_project
    if limit <= 0:
        return

    current_count = await _scalar_count(
        session,
        select(func.count()).select_from(SchemaSnapshot).where(
            SchemaSnapshot.project_space_uuid == project_space_uuid
        ),
    )
    if current_count >= limit:
        _raise_quota_exceeded("snapshot")


async def enforce_share_link_quota(
    session: AsyncSession,
    project_space_uuid: uuid.UUID,
) -> None:
    limit = settings.billing_max_share_links_per_project
    if limit <= 0:
        return

    current_count = await _scalar_count(
        session,
        select(func.count()).select_from(ShareLink).where(
            ShareLink.project_space_uuid == project_space_uuid
        ),
    )
    if current_count >= limit:
        _raise_quota_exceeded("share link")
