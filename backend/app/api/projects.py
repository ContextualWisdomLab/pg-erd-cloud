from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.db import get_read_session, get_session
from app.metrics import record_product_event
from app.permissions import require_project_member
from app.models import ProjectMember, ProjectSpace, UserAccount
from app.schemas import (
    ProjectCreateIn,
    ProjectMemberAddIn,
    ProjectMemberOut,
    ProjectOut,
)
from app.sanitize import sanitize_for_storage
from app.usage_quotas import enforce_project_quota, enforce_seat_quota

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> list[ProjectOut]:
    """List projects that the current user is a member of."""
    rows = await session.execute(
        select(ProjectSpace)
        .join(
            ProjectMember,
            ProjectMember.project_space_uuid == ProjectSpace.project_space_uuid,
        )
        .where(ProjectMember.user_account_uuid == user.user_account_uuid)
        .order_by(ProjectSpace.created_at.desc())
    )
    projects = rows.scalars().all()
    return [
        ProjectOut(project_space_uuid=p.project_space_uuid, project_name=p.project_name)
        for p in projects
    ]


@router.post("", response_model=ProjectOut)
async def create_project(
    body: ProjectCreateIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProjectOut:
    """Create a new project and add the creator as the owner."""
    try:
        await enforce_project_quota(session, user.user_account_uuid)
    except HTTPException:
        record_product_event("project", "create", "denied")
        raise

    p = ProjectSpace(
        project_space_uuid=uuid.uuid4(),
        project_name=str(sanitize_for_storage(body.project_name)),
        created_by_user_uuid=user.user_account_uuid,
        created_at=dt.datetime.now(dt.timezone.utc),
    )
    session.add(p)
    await session.flush()  # ensure project_space row exists before FK insert

    m = ProjectMember(
        project_space_uuid=p.project_space_uuid,
        user_account_uuid=user.user_account_uuid,
        project_role="owner",
        created_at=dt.datetime.now(dt.timezone.utc),
    )
    session.add(m)
    await session.commit()
    record_product_event("project", "create", "success")
    return ProjectOut(
        project_space_uuid=p.project_space_uuid, project_name=p.project_name
    )


@router.get("/{project_space_uuid}/members", response_model=list[ProjectMemberOut])
async def list_project_members(
    project_space_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> list[ProjectMemberOut]:
    """List members of a project (MVP: any member can view)."""
    # Remediation for IDOR: Only owners or editors can view all members.
    await require_project_member(
        session, project_space_uuid, user.user_account_uuid, minimum_role="editor"
    )

    rows = await session.execute(
        select(ProjectMember, UserAccount)
        .join(
            UserAccount,
            UserAccount.user_account_uuid == ProjectMember.user_account_uuid,
        )
        .where(ProjectMember.project_space_uuid == project_space_uuid)
        .order_by(ProjectMember.created_at.asc())
    )
    out: list[ProjectMemberOut] = []
    for m, u in rows.all():
        out.append(
            ProjectMemberOut(
                user_account_uuid=u.user_account_uuid,
                member_subject=u.oidc_subject,
                project_role=m.project_role,
            )
        )
    return out


async def _ensure_owner(
    session: AsyncSession, project_space_uuid: uuid.UUID, user_account_uuid: uuid.UUID
) -> None:
    row = await session.execute(
        select(ProjectMember.project_role).where(
            ProjectMember.project_space_uuid == project_space_uuid,
            ProjectMember.user_account_uuid == user_account_uuid,
        )
    )
    role = row.scalar_one_or_none()
    if role != "owner":
        raise HTTPException(status_code=403, detail="owner role required")


async def _find_user_by_subject(session: AsyncSession, subject: str) -> UserAccount | None:
    row2 = await session.execute(
        select(UserAccount).where(UserAccount.oidc_subject == subject)
    )
    return row2.scalars().first()


async def _create_user(session: AsyncSession, subject: str) -> UserAccount:
    u = UserAccount(
        user_account_uuid=uuid.uuid4(),
        oidc_subject=subject,
        display_name=None,
        created_at=dt.datetime.now(dt.timezone.utc),
    )
    session.add(u)
    await session.flush()
    return u


async def _ensure_not_changing_owner_role(
    session: AsyncSession, project_space_uuid: uuid.UUID, user_account_uuid: uuid.UUID
) -> None:
    row3 = await session.execute(
        select(ProjectMember.project_role).where(
            ProjectMember.project_space_uuid == project_space_uuid,
            ProjectMember.user_account_uuid == user_account_uuid,
        )
    )
    existing_role = row3.scalar_one_or_none()
    if existing_role == "owner":
        raise HTTPException(
            status_code=400,
            detail="cannot change owner role via invite endpoint",
        )


async def _upsert_project_member(
    session: AsyncSession,
    project_space_uuid: uuid.UUID,
    user_account_uuid: uuid.UUID,
    project_role: str,
) -> str:
    stmt = (
        insert(ProjectMember)
        .values(
            project_space_uuid=project_space_uuid,
            user_account_uuid=user_account_uuid,
            project_role=project_role,
            created_at=dt.datetime.now(dt.timezone.utc),
        )
        .on_conflict_do_update(
            index_elements=[
                ProjectMember.project_space_uuid,
                ProjectMember.user_account_uuid,
            ],
            set_={"project_role": project_role},
        )
        .returning(ProjectMember.project_role)
    )
    new_role = (await session.execute(stmt)).scalar_one()
    await session.commit()
    return str(new_role)


@router.post("/{project_space_uuid}/members", response_model=ProjectMemberOut)
async def add_project_member(
    project_space_uuid: uuid.UUID,
    body: ProjectMemberAddIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProjectMemberOut:
    """Invite/add a project member (owner-only).

    Uses a Postgres upsert to make the operation idempotent and race-safe.
    """
    await _ensure_owner(session, project_space_uuid, user.user_account_uuid)

    subject = str(sanitize_for_storage(body.member_subject)).strip()
    if not subject:
        raise HTTPException(status_code=400, detail="member_subject required")

    u = await _find_user_by_subject(session, subject)
    await enforce_seat_quota(
        session,
        owner_user_account_uuid=user.user_account_uuid,
        owner_subject=user.subject,
        candidate_user_account_uuid=(
            u.user_account_uuid if u is not None else None
        ),
    )
    if u is None:
        u = await _create_user(session, subject)
    await _ensure_not_changing_owner_role(
        session, project_space_uuid, u.user_account_uuid
    )

    new_role = await _upsert_project_member(
        session, project_space_uuid, u.user_account_uuid, body.project_role
    )

    return ProjectMemberOut(
        user_account_uuid=u.user_account_uuid,
        member_subject=u.oidc_subject,
        project_role=new_role,
    )
