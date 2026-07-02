from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing_entitlements import latest_billing_entitlement_for_subject
from app.models import (
    DbConnection,
    ProjectMember,
    ProjectSpace,
    SchemaSnapshot,
    ShareLink,
)
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


async def enforce_seat_quota(
    session: AsyncSession,
    *,
    owner_user_account_uuid: uuid.UUID,
    owner_subject: str,
    candidate_user_account_uuid: uuid.UUID | None,
) -> None:
    entitlement = await latest_billing_entitlement_for_subject(session, owner_subject)
    limit = entitlement.seat_count
    if limit is None:
        return

    owned_project_ids = select(ProjectSpace.project_space_uuid).where(
        ProjectSpace.created_by_user_uuid == owner_user_account_uuid
    )
    current_count = await _scalar_count(
        session,
        select(func.count(distinct(ProjectMember.user_account_uuid))).where(
            ProjectMember.project_space_uuid.in_(owned_project_ids)
        ),
    )
    if current_count < limit:
        return

    if candidate_user_account_uuid is not None:
        existing_count = await _scalar_count(
            session,
            select(func.count()).select_from(ProjectMember).where(
                ProjectMember.project_space_uuid.in_(owned_project_ids),
                ProjectMember.user_account_uuid == candidate_user_account_uuid,
            ),
        )
        if existing_count > 0:
            return

    _raise_quota_exceeded("seat")
