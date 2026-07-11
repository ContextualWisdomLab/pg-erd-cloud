from __future__ import annotations

import datetime as dt
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


class ApplySqlIn(BaseModel):
    """Request body for forward-engineering DDL against a connection."""

    sql: str = Field(
        min_length=1,
        max_length=262_144,
        description=(
            "Conservative PostgreSQL DDL subset with unquoted snake_case "
            "identifiers. Arbitrary SQL is rejected."
        ),
    )
    # Default to a rolled-back pre-flight; the caller must opt in to persist.
    dry_run: bool = True


class ApplySqlOut(BaseModel):
    """Result of applying forward DDL (DSN-redacted on failure)."""

    ok: bool
    dry_run: bool
    error: str | None = None


class ConnectionTestOut(BaseModel):
    """Result of a connection health probe (DSN-redacted on failure)."""

    ok: bool
    server_version: str | None = None
    error: str | None = None


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


class SchemaStatsOut(BaseModel):
    """Overview statistics for a schema snapshot."""

    schema_snapshot_uuid: uuid.UUID
    status: str
    stats: dict | None


class FkCyclesOut(BaseModel):
    """Circular foreign-key dependency findings for a snapshot."""

    schema_snapshot_uuid: uuid.UUID
    status: str
    report: dict | None


class SensitiveColumnsOut(BaseModel):
    """Compliance-scoping inventory of likely-sensitive columns."""

    schema_snapshot_uuid: uuid.UUID
    status: str
    report: dict | None


class AuditColumnsOut(BaseModel):
    """Audit-column (created_at/updated_at) convention findings."""

    schema_snapshot_uuid: uuid.UUID
    status: str
    report: dict | None


class ConstraintInventoryOut(BaseModel):
    """CHECK-rule inventory and FK delete-action risks for a snapshot."""

    schema_snapshot_uuid: uuid.UUID
    status: str
    report: dict | None


class IndexRedundancyOut(BaseModel):
    """Duplicate / prefix-redundant index findings for a snapshot."""

    schema_snapshot_uuid: uuid.UUID
    status: str
    report: dict | None


class DiagramViewCreateIn(BaseModel):
    """Request body for saving an ERD canvas view."""

    name: str = Field(min_length=1, max_length=200)
    # Opaque client layout (node positions, hidden tables, viewport). The API
    # bounds the serialized size in the endpoint to prevent abuse.
    layout_json: dict


class DiagramViewOut(BaseModel):
    """Diagram view summary."""

    diagram_view_uuid: uuid.UUID
    name: str
    created_at: dt.datetime
    updated_at: dt.datetime


class DiagramViewDetailOut(DiagramViewOut):
    """Diagram view including its layout payload."""

    layout_json: dict


class TableAnnotationUpsertIn(BaseModel):
    """Request body for creating/updating a table annotation."""

    schema_name: str = Field(min_length=1, max_length=255)
    relation_name: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=10_000)


class TableAnnotationOut(BaseModel):
    """A table annotation."""

    table_annotation_uuid: uuid.UUID
    schema_name: str
    relation_name: str
    body: str
    created_at: dt.datetime
    updated_at: dt.datetime


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


class SnapshotDiffOut(BaseModel):
    """Structured diff between two schema snapshots.

    ``status`` is ``"not_found"`` when either snapshot is missing or the caller
    is not authorized for it (uniform response avoids existence enumeration);
    ``"ok"`` with a populated ``diff`` otherwise.
    """

    base_snapshot_uuid: uuid.UUID
    target_snapshot_uuid: uuid.UUID
    status: str
    diff: dict | None


class MigrationSafetyOut(BaseModel):
    """Risk-classified analysis of migrating one snapshot to another."""

    base_snapshot_uuid: uuid.UUID
    target_snapshot_uuid: uuid.UUID
    status: str
    analysis: dict | None


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


class ApiKeyCreateIn(BaseModel):
    """Request body for creating an API key."""

    key_name: str = Field(min_length=1, max_length=128)


class ApiKeyOut(BaseModel):
    """API key metadata (never contains the secret)."""

    api_key_uuid: uuid.UUID
    key_name: str
    key_prefix: str
    created_at: dt.datetime
    revoked_at: dt.datetime | None


class ApiKeyCreatedOut(ApiKeyOut):
    """Creation response: includes the secret exactly once."""

    secret: str
