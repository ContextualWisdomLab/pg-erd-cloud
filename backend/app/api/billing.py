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
from sqlalchemy import case, desc, distinct, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Executable

from app.auth import CurrentUser, get_current_user
from app.billing_entitlements import billing_entitlement_from_events
from app.contract_state import (
    latest_contract_state_for_subject,
    normalize_billing_event_type,
)
from app.db import get_read_session, get_session
from app.models import (
    BillingEvent,
    DbConnection,
    LlmDraftUsageEvent,
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
    BillingCheckoutOut,
    BillingEventMetadataSummaryOut,
    BillingEventIn,
    BillingEventOut,
    BillingEventSummaryOut,
    BillingLlmUsageOut,
    BillingPlanChangeIn,
    BillingPlanChangeOut,
    BillingSupportAccountOut,
    BillingSupportShareLinkSummaryOut,
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
_METADATA_SUMMARY_ITEM_LIMIT = 8
_METADATA_SUMMARY_KEY_LIMIT = 96
_METADATA_SUMMARY_VALUE_LIMIT = 240

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


@dataclass(frozen=True)
class BillingLlmUsageCounts:
    request_count: int
    success_count: int
    failure_count: int
    quota_exceeded_count: int
    input_chars: int
    output_chars: int


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


def _require_allowed_target_plan(target_plan: str | None) -> None:
    if target_plan is None:
        return
    allowed_plans = _split_csv(settings.billing_allowed_plans)
    if allowed_plans and target_plan not in allowed_plans:
        raise HTTPException(
            status_code=422,
            detail="target plan is not in configured billing catalog",
        )


async def _account_status_for_subject(
    session: AsyncSession,
    subject: str,
    user_account_uuid: uuid.UUID | None,
) -> Literal["active", "deactivated", "unknown"]:
    if subject in _split_csv(settings.account_deactivated_subjects):
        return "deactivated"
    if await latest_contract_state_for_subject(session, subject) == "deactivated":
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


def _billing_month_window(month: str | None) -> tuple[str, dt.datetime, dt.datetime]:
    if month is None:
        now = utcnow()
        month = f"{now.year:04d}-{now.month:02d}"
    try:
        start = dt.datetime.strptime(month, "%Y-%m").replace(tzinfo=dt.timezone.utc)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="month must use YYYY-MM") from exc
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return month, start, end


async def _llm_usage_counts_for_account(
    session: AsyncSession,
    user_account_uuid: uuid.UUID,
    *,
    start: dt.datetime,
    end: dt.datetime,
) -> BillingLlmUsageCounts:
    result = await session.execute(
        select(
            func.count().label("request_count"),
            func.coalesce(
                func.sum(
                    case((LlmDraftUsageEvent.outcome == "success", 1), else_=0)
                ),
                0,
            ).label("success_count"),
            func.coalesce(
                func.sum(
                    case((LlmDraftUsageEvent.outcome != "success", 1), else_=0)
                ),
                0,
            ).label("failure_count"),
            func.coalesce(
                func.sum(
                    case(
                        (LlmDraftUsageEvent.outcome == "quota_exceeded", 1),
                        else_=0,
                    )
                ),
                0,
            ).label("quota_exceeded_count"),
            func.coalesce(func.sum(LlmDraftUsageEvent.input_chars), 0).label(
                "input_chars"
            ),
            func.coalesce(func.sum(LlmDraftUsageEvent.output_chars), 0).label(
                "output_chars"
            ),
        ).where(
            LlmDraftUsageEvent.user_account_uuid == user_account_uuid,
            LlmDraftUsageEvent.occurred_at >= start,
            LlmDraftUsageEvent.occurred_at < end,
        )
    )
    row = result.one()._mapping
    return BillingLlmUsageCounts(
        request_count=int(row["request_count"] or 0),
        success_count=int(row["success_count"] or 0),
        failure_count=int(row["failure_count"] or 0),
        quota_exceeded_count=int(row["quota_exceeded_count"] or 0),
        input_chars=int(row["input_chars"] or 0),
        output_chars=int(row["output_chars"] or 0),
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


def _billing_metadata_for_storage(
    payload: BillingEventIn,
    normalized_event_type: str,
) -> dict:
    metadata = _redacted_billing_metadata(payload.metadata)
    if normalized_event_type != payload.event_type:
        metadata["raw_event_type"] = payload.event_type
    return metadata


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
    outcome: Literal[
        "recorded",
        "duplicate",
        "rejected_auth",
        "rejected_config",
        "rejected_catalog",
    ],
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
        metadata_summary=_billing_metadata_summary(event.metadata_json),
    )


def _truncate_metadata_text(value: str, *, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3]}..."


def _metadata_value_text(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float | str):
        return str(value)
    if isinstance(value, list):
        return f"{len(value)} items"
    return type(value).__name__


def _billing_metadata_summary(metadata: object) -> list[BillingEventMetadataSummaryOut]:
    items: list[BillingEventMetadataSummaryOut] = []

    def add_item(path: str, value: object) -> None:
        if len(items) >= _METADATA_SUMMARY_ITEM_LIMIT:
            return
        key = _truncate_metadata_text(path, limit=_METADATA_SUMMARY_KEY_LIMIT)
        text = _truncate_metadata_text(
            _metadata_value_text(value),
            limit=_METADATA_SUMMARY_VALUE_LIMIT,
        )
        if key and text:
            items.append(BillingEventMetadataSummaryOut(key=key, value=text))

    def visit(prefix: str, value: object) -> None:
        if len(items) >= _METADATA_SUMMARY_ITEM_LIMIT:
            return
        if isinstance(value, Mapping):
            for raw_key, raw_value in value.items():
                key = str(raw_key).strip()
                if not key:
                    continue
                path = f"{prefix}.{key}" if prefix else key
                visit(path, raw_value)
                if len(items) >= _METADATA_SUMMARY_ITEM_LIMIT:
                    return
            return
        add_item(prefix or "value", value)

    visit("", metadata)
    return items


def _share_link_status(
    link: ShareLink,
    now: dt.datetime,
) -> Literal["active", "expired"]:
    if link.expires_at is None or link.expires_at > now:
        return "active"
    return "expired"


def _share_link_summary(
    link: ShareLink,
    now: dt.datetime,
) -> BillingSupportShareLinkSummaryOut:
    return BillingSupportShareLinkSummaryOut(
        share_link_uuid=link.share_link_uuid,
        project_space_uuid=link.project_space_uuid,
        permission_kind=link.permission_kind,
        status=_share_link_status(link, now),
        expires_at=link.expires_at,
        created_at=link.created_at,
    )


async def _recent_billing_event_models(
    session: AsyncSession,
    subject: str,
) -> list[BillingEvent]:
    result = await session.execute(
        select(BillingEvent)
        .where(BillingEvent.subject == subject)
        .order_by(desc(BillingEvent.received_at))
        .limit(10)
    )
    return list(result.scalars().all())


async def _recent_share_links_for_owner(
    session: AsyncSession,
    user_account_uuid: uuid.UUID,
) -> list[BillingSupportShareLinkSummaryOut]:
    owned_project_ids = select(ProjectSpace.project_space_uuid).where(
        ProjectSpace.created_by_user_uuid == user_account_uuid
    )
    result = await session.execute(
        select(ShareLink)
        .where(ShareLink.project_space_uuid.in_(owned_project_ids))
        .order_by(desc(ShareLink.created_at))
        .limit(10)
    )
    now = dt.datetime.now(dt.timezone.utc)
    return [_share_link_summary(link, now) for link in result.scalars().all()]


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


@router.get("/llm-usage", response_model=BillingLlmUsageOut)
async def get_billing_llm_usage(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> BillingLlmUsageOut:
    """Return monthly LLM draft usage for account-level billing attribution."""
    normalized_month, start, end = _billing_month_window(month)
    counts = await _llm_usage_counts_for_account(
        session,
        user.user_account_uuid,
        start=start,
        end=end,
    )
    return BillingLlmUsageOut(
        scope="account",
        month=normalized_month,
        request_count=counts.request_count,
        success_count=counts.success_count,
        failure_count=counts.failure_count,
        quota_exceeded_count=counts.quota_exceeded_count,
        input_chars=counts.input_chars,
        output_chars=counts.output_chars,
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

    account_status = await _account_status_for_subject(
        session,
        subject,
        user_account_uuid,
    )
    recent_share_links = (
        await _recent_share_links_for_owner(session, user_account_uuid)
        if user_account_uuid is not None
        else []
    )
    recent_billing_event_models = await _recent_billing_event_models(
        session,
        subject,
    )

    return BillingSupportAccountOut(
        subject=subject,
        user_account_uuid=user_account_uuid,
        account_status=account_status,
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
        billing_entitlement=billing_entitlement_from_events(
            recent_billing_event_models,
        ),
        recent_share_links=recent_share_links,
        recent_billing_events=[
            _billing_event_summary(event) for event in recent_billing_event_models
        ],
    )


@router.post("/plan-change", response_model=BillingPlanChangeOut)
async def request_billing_plan_change(
    payload: BillingPlanChangeIn,
    user: CurrentUser = Depends(get_current_user),
) -> BillingPlanChangeOut:
    """Return the configured billing action for a requested plan change."""
    del user
    _require_allowed_target_plan(payload.target_plan)

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


@router.post("/checkout", response_model=BillingCheckoutOut)
async def request_billing_checkout(
    payload: BillingPlanChangeIn,
    user: CurrentUser = Depends(get_current_user),
) -> BillingCheckoutOut:
    """Return the configured billing checkout action for a requested plan."""
    del user
    _require_allowed_target_plan(payload.target_plan)

    if settings.billing_checkout_url:
        return BillingCheckoutOut(
            action="checkout_redirect",
            target_plan=payload.target_plan,
            billing_checkout_url=_portal_url_with_target_plan(
                settings.billing_checkout_url,
                payload.target_plan,
            ),
            billing_support_url=settings.billing_support_url,
            message="Open checkout to start this plan.",
        )

    if settings.billing_support_url:
        return BillingCheckoutOut(
            action="contact_support",
            target_plan=payload.target_plan,
            billing_checkout_url=None,
            billing_support_url=settings.billing_support_url,
            message="Contact billing support to start this plan.",
        )

    raise HTTPException(
        status_code=503,
        detail="billing checkout path is not configured",
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
    normalized_event_type = normalize_billing_event_type(
        payload.event_type,
        provider=payload.provider,
    )
    normalized_payload = payload.model_copy(
        update={"event_type": normalized_event_type},
    )
    try:
        await _require_valid_billing_webhook_auth(
            request=request,
            billing_webhook_secret=billing_webhook_secret,
            billing_webhook_signature=billing_webhook_signature,
        )
    except HTTPException as exc:
        _record_billing_event_metric(
            normalized_payload,
            "rejected_config" if exc.status_code == 503 else "rejected_auth",
        )
        raise

    existing = await _find_billing_event(
        session,
        provider=normalized_payload.provider,
        provider_event_id=normalized_payload.provider_event_id,
    )
    if existing is not None:
        _record_billing_event_metric(normalized_payload, "duplicate")
        return _billing_event_response(event=existing, action="duplicate")
    try:
        _require_allowed_target_plan(normalized_payload.target_plan)
    except HTTPException:
        _record_billing_event_metric(normalized_payload, "rejected_catalog")
        raise

    now = utcnow()
    event = BillingEvent(
        billing_event_uuid=uuid.uuid4(),
        provider=normalized_payload.provider,
        provider_event_id=normalized_payload.provider_event_id,
        event_type=normalized_payload.event_type,
        subject=normalized_payload.subject,
        target_plan=normalized_payload.target_plan,
        event_status="recorded",
        occurred_at=normalized_payload.occurred_at or now,
        received_at=now,
        metadata_json=_billing_metadata_for_storage(
            payload,
            normalized_payload.event_type,
        ),
    )
    session.add(event)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        duplicate = await _find_billing_event(
            session,
            provider=normalized_payload.provider,
            provider_event_id=normalized_payload.provider_event_id,
        )
        if duplicate is None:
            raise
        _record_billing_event_metric(normalized_payload, "duplicate")
        return _billing_event_response(event=duplicate, action="duplicate")

    _record_billing_event_metric(normalized_payload, "recorded")
    return _billing_event_response(event=event, action="recorded")
