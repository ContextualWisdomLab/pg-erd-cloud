from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

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


class BillingUsageOut(BaseModel):
    """Read-only usage counters for billing and license operations."""

    scope: Literal["owned_projects"]
    license_mode: Literal["off", "required"]
    license_verifier: Literal[
        "none", "static_key", "signed_token", "static_key_and_signed_token"
    ]
    project_count: int = Field(ge=0)
    seat_count: int = Field(ge=0)
    connection_count: int = Field(ge=0)
    snapshot_count: int = Field(ge=0)
    share_link_count: int = Field(ge=0)
    active_share_link_count: int = Field(ge=0)
