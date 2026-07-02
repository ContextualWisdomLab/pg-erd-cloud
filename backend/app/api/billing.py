from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import desc, distinct, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Executable

from app.auth import CurrentUser, get_current_user
from app.db import get_read_session, get_session
from app.models import (
    BillingEvent,
    DbConnection,
    ProjectMember,
    ProjectSpace,
    SchemaSnapshot,
    ShareLink,
    UserAccount,
    utcnow,
)
from app.metrics import BILLING_EVENTS_TOTAL
from app.sanitize import sanitize_for_storage
from app.schemas import (
    BillingEventIn,
    BillingEventOut,
    BillingEventSummaryOut,
    BillingPlanChangeIn,
    BillingPlanChangeOut,
    BillingSupportAccountOut,
    BillingUsageOut,
)
from app.settings import settings

router = APIRouter(prefix="/api/billing", tags=["billing"])
_BILLING_WEBHOOK_SECRET_HEADER = "X-BILLING-WEBHOOK-SECRET"
_BILLING_WEBHOOK_SIGNATURE_HEADER = "X-BILLING-WEBHOOK-SIGNATURE"
_SENSITIVE_METADATA_KEY_PARTS = (
    "api_key",
    "authorization",
    "card",
    "client_secret",
    "dsn",
    "password",
    "secret",
    "token",
)

LicenseVerifierKind = Literal[
    "none", "static_key", "signed_token", "static_key_and_signed_token"
]


@dataclass(frozen=True)
class BillingUsageCounts:
    project_count: int
    seat_count: int
    connection_count: int
    snapshot_count: int
    share_link_count: int
    active_share_link_count: int


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


def _split_csv(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def _account_status_for_subject(
    subject: str,
    user_account_uuid: uuid.UUID | None,
) -> Literal["active", "deactivated", "unknown"]:
    if subject in _split_csv(settings.account_deactivated_subjects):
        return "deactivated"
    if user_account_uuid is None:
        return "unknown"
    return "active"


def _require_support_operator(user: CurrentUser) -> None:
    if user.subject not in _split_csv(settings.support_operator_subjects):
        raise HTTPException(status_code=403, detail="support operator role required")


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


async def _usage_counts_for_owner(
    session: AsyncSession,
    user_account_uuid: uuid.UUID,
) -> BillingUsageCounts:
    owned_project_ids = select(ProjectSpace.project_space_uuid).where(
        ProjectSpace.created_by_user_uuid == user_account_uuid
    )
    now = dt.datetime.now(dt.timezone.utc)

    return BillingUsageCounts(
        project_count=await _scalar_count(
            session,
            select(func.count())
            .select_from(ProjectSpace)
            .where(ProjectSpace.created_by_user_uuid == user_account_uuid),
        ),
        seat_count=await _scalar_count(
            session,
            select(func.count(distinct(ProjectMember.user_account_uuid))).where(
                ProjectMember.project_space_uuid.in_(owned_project_ids)
            ),
        ),
        connection_count=await _scalar_count(
            session,
            select(func.count()).select_from(DbConnection).where(
                DbConnection.project_space_uuid.in_(owned_project_ids)
            ),
        ),
        snapshot_count=await _scalar_count(
            session,
            select(func.count()).select_from(SchemaSnapshot).where(
                SchemaSnapshot.project_space_uuid.in_(owned_project_ids)
            ),
        ),
        share_link_count=await _scalar_count(
            session,
            select(func.count()).select_from(ShareLink).where(
                ShareLink.project_space_uuid.in_(owned_project_ids)
            ),
        ),
        active_share_link_count=await _scalar_count(
            session,
            select(func.count()).select_from(ShareLink).where(
                ShareLink.project_space_uuid.in_(owned_project_ids),
                or_(ShareLink.expires_at.is_(None), ShareLink.expires_at > now),
            ),
        ),
    )


def _redact_billing_metadata(value: object) -> object:
    if isinstance(value, Mapping):
        redacted: dict[str, object] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            key_lower = key.lower()
            if any(part in key_lower for part in _SENSITIVE_METADATA_KEY_PARTS):
                redacted[key] = "[redacted]"
            else:
                redacted[key] = _redact_billing_metadata(raw_value)
        return sanitize_for_storage(redacted)
    if isinstance(value, list):
        return [_redact_billing_metadata(item) for item in value]
    return sanitize_for_storage(value)


def _redacted_billing_metadata(metadata: Mapping[str, object]) -> dict:
    redacted = _redact_billing_metadata(metadata)
    if isinstance(redacted, dict):
        return redacted
    return {}


def _expected_billing_signature(raw_body: bytes) -> str:
    secret = settings.billing_webhook_signature_secret
    if secret is None:
        raise RuntimeError("billing webhook signature secret is not configured")
    return hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()


def _signature_value(header_value: str) -> str:
    signature = header_value.strip()
    if signature.startswith("sha256="):
        return signature.removeprefix("sha256=")
    return signature


async def _require_valid_billing_webhook_auth(
    *,
    request: Request,
    billing_webhook_secret: str | None,
    billing_webhook_signature: str | None,
) -> None:
    if not (settings.billing_webhook_secret or settings.billing_webhook_signature_secret):
        raise HTTPException(
            status_code=503,
            detail="billing webhook secret is not configured",
        )

    if settings.billing_webhook_secret and (
        not billing_webhook_secret
        or not hmac.compare_digest(
            billing_webhook_secret,
            settings.billing_webhook_secret,
        )
    ):
        raise HTTPException(status_code=401, detail="invalid billing webhook secret")

    if settings.billing_webhook_signature_secret:
        if not billing_webhook_signature:
            raise HTTPException(
                status_code=401,
                detail="invalid billing webhook signature",
            )
        expected = _expected_billing_signature(await request.body())
        provided = _signature_value(billing_webhook_signature)
        if not hmac.compare_digest(provided, expected):
            raise HTTPException(
                status_code=401,
                detail="invalid billing webhook signature",
            )


async def _find_billing_event(
    session: AsyncSession,
    provider: str,
    provider_event_id: str,
) -> BillingEvent | None:
    result = await session.execute(
        select(BillingEvent).where(
            BillingEvent.provider == provider,
            BillingEvent.provider_event_id == provider_event_id,
        )
    )
    return result.scalar_one_or_none()


def _billing_event_response(
    *,
    event: BillingEvent,
    action: Literal["recorded", "duplicate"],
) -> BillingEventOut:
    message = (
        "Billing event recorded for reconciliation."
        if action == "recorded"
        else "Billing event was already recorded; duplicate ignored."
    )
    return BillingEventOut(
        action=action,
        billing_event_uuid=event.billing_event_uuid,
        provider=event.provider,
        provider_event_id=event.provider_event_id,
        event_type=event.event_type,
        subject=event.subject,
        target_plan=event.target_plan,
        status="recorded",
        occurred_at=event.occurred_at,
        received_at=event.received_at,
        message=message,
    )


def _record_billing_event_metric(
    payload: BillingEventIn,
    outcome: Literal["recorded", "duplicate", "rejected_auth", "rejected_config"],
) -> None:
    BILLING_EVENTS_TOTAL.labels(
        provider=payload.provider,
        event_type=payload.event_type,
        outcome=outcome,
    ).inc()


def _billing_event_summary(event: BillingEvent) -> BillingEventSummaryOut:
    return BillingEventSummaryOut(
        billing_event_uuid=event.billing_event_uuid,
        provider=event.provider,
        provider_event_id=event.provider_event_id,
        event_type=event.event_type,
        target_plan=event.target_plan,
        status="recorded",
        occurred_at=event.occurred_at,
        received_at=event.received_at,
    )


async def _recent_billing_events(
    session: AsyncSession,
    subject: str,
) -> list[BillingEventSummaryOut]:
    result = await session.execute(
        select(BillingEvent)
        .where(BillingEvent.subject == subject)
        .order_by(desc(BillingEvent.received_at))
        .limit(10)
    )
    return [_billing_event_summary(event) for event in result.scalars().all()]


@router.get("/usage", response_model=BillingUsageOut)
async def get_billing_usage(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> BillingUsageOut:
    """Return current account usage counters for billing/license operations."""
    usage_counts = await _usage_counts_for_owner(session, user.user_account_uuid)

    return BillingUsageOut(
        scope="owned_projects",
        account_status="active",
        license_mode=settings.license_mode,
        license_verifier=_license_verifier_kind(),
        billing_portal_url=settings.billing_portal_url,
        billing_support_url=settings.billing_support_url,
        account_reactivation_url=settings.account_reactivation_url,
        project_count=usage_counts.project_count,
        seat_count=usage_counts.seat_count,
        connection_count=usage_counts.connection_count,
        snapshot_count=usage_counts.snapshot_count,
        share_link_count=usage_counts.share_link_count,
        active_share_link_count=usage_counts.active_share_link_count,
        project_limit=settings.billing_max_projects_per_user,
        connection_limit=settings.billing_max_connections_per_project,
        snapshot_limit=settings.billing_max_snapshots_per_project,
        share_link_limit=settings.billing_max_share_links_per_project,
    )


@router.get("/support/account", response_model=BillingSupportAccountOut)
async def get_support_account_billing(
    subject: str = Query(
        min_length=1,
        max_length=128,
        pattern=r"^[^\x00-\x1F\x7F]+$",
    ),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> BillingSupportAccountOut:
    """Return read-only billing/account diagnostics for support operators."""
    _require_support_operator(user)

    account_result = await session.execute(
        select(UserAccount).where(UserAccount.oidc_subject == subject)
    )
    account = account_result.scalar_one_or_none()
    user_account_uuid = account.user_account_uuid if account is not None else None
    usage_counts = (
        await _usage_counts_for_owner(session, user_account_uuid)
        if user_account_uuid is not None
        else BillingUsageCounts(
            project_count=0,
            seat_count=0,
            connection_count=0,
            snapshot_count=0,
            share_link_count=0,
            active_share_link_count=0,
        )
    )

    return BillingSupportAccountOut(
        subject=subject,
        user_account_uuid=user_account_uuid,
        account_status=_account_status_for_subject(subject, user_account_uuid),
        license_mode=settings.license_mode,
        license_verifier=_license_verifier_kind(),
        billing_portal_url=settings.billing_portal_url,
        billing_support_url=settings.billing_support_url,
        account_reactivation_url=settings.account_reactivation_url,
        project_count=usage_counts.project_count,
        seat_count=usage_counts.seat_count,
        connection_count=usage_counts.connection_count,
        snapshot_count=usage_counts.snapshot_count,
        share_link_count=usage_counts.share_link_count,
        active_share_link_count=usage_counts.active_share_link_count,
        recent_billing_events=await _recent_billing_events(session, subject),
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


@router.post("/events", response_model=BillingEventOut)
async def ingest_billing_event(
    request: Request,
    payload: BillingEventIn,
    billing_webhook_secret: str | None = Header(
        default=None,
        alias=_BILLING_WEBHOOK_SECRET_HEADER,
    ),
    billing_webhook_signature: str | None = Header(
        default=None,
        alias=_BILLING_WEBHOOK_SIGNATURE_HEADER,
    ),
    session: AsyncSession = Depends(get_session),
) -> BillingEventOut:
    """Record a provider-neutral billing event for support reconciliation."""
    try:
        await _require_valid_billing_webhook_auth(
            request=request,
            billing_webhook_secret=billing_webhook_secret,
            billing_webhook_signature=billing_webhook_signature,
        )
    except HTTPException as exc:
        _record_billing_event_metric(
            payload,
            "rejected_config" if exc.status_code == 503 else "rejected_auth",
        )
        raise

    existing = await _find_billing_event(
        session,
        provider=payload.provider,
        provider_event_id=payload.provider_event_id,
    )
    if existing is not None:
        _record_billing_event_metric(payload, "duplicate")
        return _billing_event_response(event=existing, action="duplicate")

    now = utcnow()
    event = BillingEvent(
        billing_event_uuid=uuid.uuid4(),
        provider=payload.provider,
        provider_event_id=payload.provider_event_id,
        event_type=payload.event_type,
        subject=payload.subject,
        target_plan=payload.target_plan,
        event_status="recorded",
        occurred_at=payload.occurred_at or now,
        received_at=now,
        metadata_json=_redacted_billing_metadata(payload.metadata),
    )
    session.add(event)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        duplicate = await _find_billing_event(
            session,
            provider=payload.provider,
            provider_event_id=payload.provider_event_id,
        )
        if duplicate is None:
            raise
        _record_billing_event_metric(payload, "duplicate")
        return _billing_event_response(event=duplicate, action="duplicate")

    _record_billing_event_metric(payload, "recorded")
    return _billing_event_response(event=event, action="recorded")
