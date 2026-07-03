from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class ProjectCreateIn(BaseModel):
    """Request body for creating a project."""

    project_name: str = Field(min_length=1, max_length=255)


class ProjectOut(BaseModel):
    """Project summary returned by API."""

    project_space_uuid: uuid.UUID
    project_name: str


class ProjectMemberAddIn(BaseModel):
    """Request body for inviting/adding a project member."""

    member_subject: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[^\s\x00-\x1F\x7F]+$",
        description="OIDC sub, or dev:<name> in dev mode",
    )
    # MVP: restrict to non-owner roles. Owner is assigned at project creation.
    project_role: Literal["viewer", "editor"] = Field(default="viewer")


class ProjectMemberOut(BaseModel):
    """Project member representation returned by API."""

    user_account_uuid: uuid.UUID
    member_subject: str
    project_role: str


class ConnectionCreateIn(BaseModel):
    """Request body for creating a DB connection."""

    conn_name: str = Field(min_length=1, max_length=128)
    dsn: str = Field(
        min_length=1,
        max_length=4096,
        description=("PostgreSQL or Snowflake connection string. Not logged."),
    )


class ConnectionOut(BaseModel):
    """Connection summary returned by API."""

    db_connection_uuid: uuid.UUID
    conn_name: str


class SnapshotCreateIn(BaseModel):
    """Request body for creating a schema snapshot."""

    db_connection_uuid: uuid.UUID
    schema_filter: str | None = Field(
        default=None,
        description=(
            "If set, only introspect this schema (unquoted database identifier)"
        ),
        min_length=1,
        max_length=63,
        pattern=r"^[A-Za-z_][A-Za-z0-9_$]{0,62}$",
    )


class SnapshotOut(BaseModel):
    """Snapshot summary returned by API."""

    schema_snapshot_uuid: uuid.UUID
    status: str
    schema_filter: str | None


class SnapshotDetailOut(BaseModel):
    """Snapshot detail returned by API."""

    schema_snapshot_uuid: uuid.UUID
    status: str
    schema_filter: str | None
    error_message: str | None
    snapshot_json: dict | None


class ShareLinkCreateIn(BaseModel):
    """Request body for creating a public project share link."""

    expires_in_hours: int | None = Field(
        default=None,
        ge=0,
        le=8760,
        description=(
            "Override the default share-link TTL. Use 0 only for an explicit "
            "non-expiring operational exception."
        ),
    )


class ShareLinkOut(BaseModel):
    """Share link representation returned by API."""

    share_link_uuid: uuid.UUID
    permission_kind: str
    url_path: str
    expires_at: dt.datetime | None
    created_at: dt.datetime


class MeOut(BaseModel):
    """Current user payload returned by /me."""

    user_account_uuid: uuid.UUID
    subject: str
    display_name: str | None
    support_operator: bool = False


class BillingUsageOut(BaseModel):
    """Read-only usage counters for billing and license operations."""

    scope: Literal["owned_projects"]
    account_status: Literal["active"]
    license_mode: Literal["off", "required"]
    license_verifier: Literal[
        "none", "static_key", "signed_token", "static_key_and_signed_token"
    ]
    billing_portal_url: str | None
    billing_support_url: str | None
    account_reactivation_url: str | None
    project_count: int = Field(ge=0)
    seat_count: int = Field(ge=0)
    connection_count: int = Field(ge=0)
    snapshot_count: int = Field(ge=0)
    share_link_count: int = Field(ge=0)
    active_share_link_count: int = Field(ge=0)
    project_limit: int = Field(ge=0)
    connection_limit: int = Field(ge=0)
    snapshot_limit: int = Field(ge=0)
    share_link_limit: int = Field(ge=0)


class BillingLlmUsageOut(BaseModel):
    """Monthly account-level LLM draft usage for billing attribution."""

    scope: Literal["account"]
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    request_count: int = Field(ge=0)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    quota_exceeded_count: int = Field(ge=0)
    input_chars: int = Field(ge=0)
    output_chars: int = Field(ge=0)


class BillingPlanChangeIn(BaseModel):
    """Request body for starting a billing plan-change flow."""

    target_plan: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$",
    )


class BillingPlanChangeOut(BaseModel):
    """Billing plan-change action returned to the client."""

    action: Literal["portal_redirect", "contact_support"]
    target_plan: str
    billing_portal_url: str | None
    billing_support_url: str | None
    message: str


class BillingCheckoutOut(BaseModel):
    """Billing checkout action returned to the client."""

    action: Literal["checkout_redirect", "contact_support"]
    target_plan: str
    billing_checkout_url: str | None
    billing_support_url: str | None
    message: str


class BillingEventIn(BaseModel):
    """Provider-neutral billing/license event for reconciliation."""

    provider: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$",
    )
    provider_event_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[^\s\x00-\x1F\x7F]+$",
    )
    event_type: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$",
    )
    subject: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[^\x00-\x1F\x7F]+$",
    )
    target_plan: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$",
    )
    occurred_at: dt.datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BillingEventOut(BaseModel):
    """Billing reconciliation event status returned to the caller."""

    action: Literal["recorded", "duplicate"]
    billing_event_uuid: uuid.UUID
    provider: str
    provider_event_id: str
    event_type: str
    subject: str
    target_plan: str | None
    status: Literal["recorded"]
    occurred_at: dt.datetime
    received_at: dt.datetime
    message: str


class BillingEventMetadataSummaryOut(BaseModel):
    """Redacted billing metadata field safe for support diagnostics."""

    key: str = Field(min_length=1, max_length=96)
    value: str = Field(min_length=1, max_length=240)


class BillingEventSummaryOut(BaseModel):
    """Billing event summary safe for support diagnostics."""

    billing_event_uuid: uuid.UUID
    provider: str
    provider_event_id: str
    event_type: str
    target_plan: str | None
    status: Literal["recorded"]
    occurred_at: dt.datetime
    received_at: dt.datetime
    metadata_summary: list[BillingEventMetadataSummaryOut] = Field(
        default_factory=list
    )


class BillingSupportShareLinkSummaryOut(BaseModel):
    """Share-link summary safe for support diagnostics."""

    share_link_uuid: uuid.UUID
    project_space_uuid: uuid.UUID
    permission_kind: str
    status: Literal["active", "expired"]
    expires_at: dt.datetime | None
    created_at: dt.datetime


class BillingEntitlementOut(BaseModel):
    """Latest provider-neutral entitlement evidence for a billing subject."""

    plan: str | None
    seat_count: int | None = Field(default=None, ge=1)
    source_provider: str | None
    source_provider_event_id: str | None
    source_event_type: str | None
    source_occurred_at: dt.datetime | None


class BillingSeatReconciliationCandidateOut(BaseModel):
    """Support-visible member candidate for manual seat deprovisioning review."""

    member_subject: str
    project_count: int = Field(ge=0)


class BillingSeatReconciliationOut(BaseModel):
    """Read-only comparison between contracted seats and active app seats."""

    status: Literal["unknown_account", "not_configured", "within_limit", "over_limit"]
    contracted_seat_count: int | None = Field(default=None, ge=1)
    active_seat_count: int = Field(ge=0)
    seats_over_limit: int = Field(ge=0)
    deprovisioning_required: bool
    deprovisioning_candidates: list[BillingSeatReconciliationCandidateOut]


class BillingSupportAccountOut(BaseModel):
    """Read-only account diagnostics for authorized support operators."""

    subject: str
    user_account_uuid: uuid.UUID | None
    account_status: Literal["active", "deactivated", "unknown"]
    license_mode: Literal["off", "required"]
    license_verifier: Literal[
        "none", "static_key", "signed_token", "static_key_and_signed_token"
    ]
    billing_portal_url: str | None
    billing_support_url: str | None
    account_reactivation_url: str | None
    project_count: int = Field(ge=0)
    seat_count: int = Field(ge=0)
    connection_count: int = Field(ge=0)
    snapshot_count: int = Field(ge=0)
    share_link_count: int = Field(ge=0)
    active_share_link_count: int = Field(ge=0)
    billing_entitlement: BillingEntitlementOut
    billing_seat_reconciliation: BillingSeatReconciliationOut
    llm_usage_current_month: BillingLlmUsageOut
    recent_share_links: list[BillingSupportShareLinkSummaryOut]
    recent_billing_events: list[BillingEventSummaryOut]
