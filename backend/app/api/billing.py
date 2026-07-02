from __future__ import annotations

import datetime as dt
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Executable

from app.auth import CurrentUser, get_current_user
from app.db import get_read_session
from app.models import (
    DbConnection,
    ProjectMember,
    ProjectSpace,
    SchemaSnapshot,
    ShareLink,
)
from app.schemas import BillingPlanChangeIn, BillingPlanChangeOut, BillingUsageOut
from app.settings import settings

router = APIRouter(prefix="/api/billing", tags=["billing"])

LicenseVerifierKind = Literal[
    "none", "static_key", "signed_token", "static_key_and_signed_token"
]


def _license_verifier_kind() -> LicenseVerifierKind:
    has_static_key = bool(settings.license_key)
    has_signed_token_verifier = bool(settings.license_public_key)
    if has_static_key and has_signed_token_verifier:
        return "static_key_and_signed_token"
    if has_signed_token_verifier:
        return "signed_token"
    if has_static_key:
        return "static_key"
    return "none"


async def _scalar_count(session: AsyncSession, stmt: Executable) -> int:
    result = await session.execute(stmt)
    value = result.scalar_one()
    return int(value or 0)


def _portal_url_with_target_plan(base_url: str, target_plan: str) -> str:
    parts = urlsplit(base_url)
    query_items = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key != "target_plan"
    ]
    query_items.append(("target_plan", target_plan))
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query_items),
            parts.fragment,
        )
    )


@router.get("/usage", response_model=BillingUsageOut)
async def get_billing_usage(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> BillingUsageOut:
    """Return current account usage counters for billing/license operations."""
    owned_project_ids = select(ProjectSpace.project_space_uuid).where(
        ProjectSpace.created_by_user_uuid == user.user_account_uuid
    )
    now = dt.datetime.now(dt.timezone.utc)

    project_count = await _scalar_count(
        session,
        select(func.count())
        .select_from(ProjectSpace)
        .where(ProjectSpace.created_by_user_uuid == user.user_account_uuid),
    )
    seat_count = await _scalar_count(
        session,
        select(func.count(distinct(ProjectMember.user_account_uuid))).where(
            ProjectMember.project_space_uuid.in_(owned_project_ids)
        ),
    )
    connection_count = await _scalar_count(
        session,
        select(func.count()).select_from(DbConnection).where(
            DbConnection.project_space_uuid.in_(owned_project_ids)
        ),
    )
    snapshot_count = await _scalar_count(
        session,
        select(func.count()).select_from(SchemaSnapshot).where(
            SchemaSnapshot.project_space_uuid.in_(owned_project_ids)
        ),
    )
    share_link_count = await _scalar_count(
        session,
        select(func.count()).select_from(ShareLink).where(
            ShareLink.project_space_uuid.in_(owned_project_ids)
        ),
    )
    active_share_link_count = await _scalar_count(
        session,
        select(func.count()).select_from(ShareLink).where(
            ShareLink.project_space_uuid.in_(owned_project_ids),
            or_(ShareLink.expires_at.is_(None), ShareLink.expires_at > now),
        ),
    )

    return BillingUsageOut(
        scope="owned_projects",
        account_status="active",
        license_mode=settings.license_mode,
        license_verifier=_license_verifier_kind(),
        billing_portal_url=settings.billing_portal_url,
        billing_support_url=settings.billing_support_url,
        account_reactivation_url=settings.account_reactivation_url,
        project_count=project_count,
        seat_count=seat_count,
        connection_count=connection_count,
        snapshot_count=snapshot_count,
        share_link_count=share_link_count,
        active_share_link_count=active_share_link_count,
        project_limit=settings.billing_max_projects_per_user,
        connection_limit=settings.billing_max_connections_per_project,
        snapshot_limit=settings.billing_max_snapshots_per_project,
        share_link_limit=settings.billing_max_share_links_per_project,
    )


@router.post("/plan-change", response_model=BillingPlanChangeOut)
async def request_billing_plan_change(
    payload: BillingPlanChangeIn,
    user: CurrentUser = Depends(get_current_user),
) -> BillingPlanChangeOut:
    """Return the configured billing action for a requested plan change."""
    del user

    if settings.billing_portal_url:
        return BillingPlanChangeOut(
            action="portal_redirect",
            target_plan=payload.target_plan,
            billing_portal_url=_portal_url_with_target_plan(
                settings.billing_portal_url,
                payload.target_plan,
            ),
            billing_support_url=settings.billing_support_url,
            message="Open the billing portal to request or complete this plan change.",
        )

    if settings.billing_support_url:
        return BillingPlanChangeOut(
            action="contact_support",
            target_plan=payload.target_plan,
            billing_portal_url=None,
            billing_support_url=settings.billing_support_url,
            message="Contact billing support to request or complete this plan change.",
        )

    raise HTTPException(
        status_code=503,
        detail="billing plan change path is not configured",
    )
