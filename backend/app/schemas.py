from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class ProjectCreateIn(BaseModel):
    """Request body for creating a project."""

    project_name: str = Field(
        min_length=1,
        max_length=255,
        pattern=r"^[^\x00-\x1F\x7F]+$",
    )


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

    conn_name: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[^\x00-\x1F\x7F]+$",
    )
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


class WideTablesOut(BaseModel):
    """Wide / denormalized table findings for a snapshot."""

    schema_snapshot_uuid: uuid.UUID
    status: str
    report: dict | None


class InferredRelationshipOut(BaseModel):
    """An implicit (undeclared) foreign-key relationship inferred from names."""

    child_schema: str
    child_table: str
    child_column: str
    parent_schema: str
    parent_table: str
    parent_column: str
    confidence: str
    reason: str


class MeOut(BaseModel):
    """Current user payload returned by /me."""

    user_account_uuid: uuid.UUID
    subject: str
    display_name: str | None


class NamingLintOut(BaseModel):
    """Naming-convention findings for a snapshot's identifiers."""

    schema_snapshot_uuid: uuid.UUID
    status: str
    report: dict | None
