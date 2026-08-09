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
    project_role: Literal["viewer", "editor", "deployer"] = Field(default="viewer")


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


class SchemaModelCreateIn(BaseModel):
    """Create a named editable model and its first immutable revision."""

    model_name: str = Field(
        min_length=1, max_length=255, pattern=r"^[^\x00-\x1F\x7F]+$"
    )
    model_json: dict
    base_schema_snapshot_uuid: uuid.UUID | None = None


class SchemaModelReviseIn(BaseModel):
    """Save a successor revision under optimistic concurrency control."""

    model_json: dict
    base_schema_snapshot_uuid: uuid.UUID | None = None


class SchemaModelDetailOut(BaseModel):
    """Editable model identity together with one immutable revision."""

    schema_model_uuid: uuid.UUID
    model_name: str
    schema_model_revision_uuid: uuid.UUID
    revision_number: int
    revision_digest: str
    model_json: dict
    base_schema_snapshot_uuid: uuid.UUID | None


class MigrationPlanCreateIn(BaseModel):
    """Bind one model revision to an exact target connection and snapshot."""

    db_connection_uuid: uuid.UUID
    base_schema_snapshot_uuid: uuid.UUID


class MigrationPlanObjectRef(BaseModel):
    """Structured PostgreSQL object identity carried beside rendered SQL."""

    database: str | None = None
    schema_name: str | None = None
    table_name: str | None = None
    column_name: str | None = None


class MigrationPlanRisk(BaseModel):
    """Conservative operational and data-integrity risk for one statement."""

    severity: Literal["safe", "warning", "destructive"]
    lock_mode: str
    possible_rewrite: bool
    table_scan: bool
    data_loss: bool
    detail: str


class MigrationPlanStatement(BaseModel):
    """One server-compiled statement and its execution authority metadata."""

    kind: str
    target: str
    object_ref: MigrationPlanObjectRef
    sql: str
    transactional: bool
    dependencies: list[str]
    dependency_refs: list[MigrationPlanObjectRef]
    reversible: bool
    risk: MigrationPlanRisk
    required_privileges: list[str]
    preconditions: list[dict[str, object]]


class MigrationPlanBlocker(BaseModel):
    """Unsupported semantic change that suppresses executable statements."""

    code: str
    object: str
    object_ref: MigrationPlanObjectRef
    detail: str


class MigrationPlanRiskSummary(BaseModel):
    """Statement counts grouped by conservative risk severity."""

    safe: int
    warning: int
    destructive: int


class MigrationPlanOut(BaseModel):
    """Immutable structured plan preview returned for review and dry run."""

    migration_plan_uuid: uuid.UUID
    project_space_uuid: uuid.UUID
    schema_model_revision_uuid: uuid.UUID
    db_connection_uuid: uuid.UUID
    base_schema_snapshot_uuid: uuid.UUID
    plan_digest: str
    base_digest: str
    target_digest: str
    compiler_version: str
    snapshot_contract_version: int = Field(ge=1)
    postgresql_major: int = Field(ge=14, le=18)
    created_by_user_uuid: uuid.UUID
    created_at: dt.datetime
    can_dry_run: bool
    requires_destructive_confirmation: bool
    statements: list[MigrationPlanStatement]
    proposed_statements: list[MigrationPlanStatement]
    blockers: list[MigrationPlanBlocker]
    risk_summary: MigrationPlanRiskSummary
    expires_at: dt.datetime


class MigrationRunEventOut(BaseModel):
    """One ordered, sanitized event in a durable migration-run history."""

    sequence_number: int = Field(ge=1)
    event_type: str
    state_before: str | None
    state_after: str
    evidence: dict[str, object]
    previous_event_digest: str | None
    event_digest: str
    actor_user_uuid: uuid.UUID | None
    created_at: dt.datetime


class MigrationRunOut(BaseModel):
    """Authorized immutable view of one durable run and its event history."""

    migration_run_uuid: uuid.UUID
    project_space_uuid: uuid.UUID
    migration_plan_uuid: uuid.UUID
    run_kind: Literal["dry_run", "apply"]
    state: str
    state_version: int = Field(ge=1)
    plan_digest: str
    requested_by_user_uuid: uuid.UUID
    cancellation_requested: bool
    observed_base_digest: str | None
    evidence: dict[str, object]
    error_code: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    started_at: dt.datetime | None
    finished_at: dt.datetime | None
    events: list[MigrationRunEventOut]


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


class DbmlConvertIn(BaseModel):
    """Request body for converting DBML text into a snapshot."""

    dbml: str = Field(min_length=1, max_length=524_288)
    include_ddl: bool = True
    dialect: Literal["postgresql", "snowflake"] = "postgresql"


class DbmlConvertOut(BaseModel):
    """DBML conversion result: snapshot JSON plus optional DDL."""

    snapshot_json: dict
    ddl: str | None = None
    tables: int
    foreign_keys: int


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
