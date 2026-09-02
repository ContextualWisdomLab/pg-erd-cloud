from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.db import get_session
from app.ddl.export import snapshot_json_to_sql
from app.models import (
    ProjectMember,
    SchemaSnapshot,
    SchemaSnapshotData,
    ShareLink,
)
from app.spec.index_design import generate_index_design_spec
from app.spec.reversing import generate_reversing_spec
from app.settings import settings

router = APIRouter(prefix="/api", tags=["share"])


# Versioned public snapshot DTO v1. Keys are scoped to their exact location so
# a newly added internal field cannot become public merely because its name is
# already valid somewhere else in the snapshot document.
_PUBLIC_SNAPSHOT_V1_ROOT_KEYS = frozenset(
    {
        "source",
        "captured_at",
        "server_version",
        "source_dialect",
        "database_dialect",
        "database_name",
        "schema_filter",
    }
)

_PUBLIC_SNAPSHOT_V1_ROW_KEYS = {
    "schemas": frozenset({"schema_oid", "schema_name"}),
    "relations": frozenset(
        {
            "schema_name",
            "relation_oid",
            "relation_name",
            "relation_kind",
            "is_partition",
            "partition_key",
            "partition_bound",
            "partition_parent_oid",
            "partition_parent_schema",
            "partition_parent_name",
            "tablespace_name",
        }
    ),
    "columns": frozenset(
        {
            "schema_name",
            "relation_oid",
            "relation_name",
            "relation_kind",
            "column_position",
            "column_name",
            "data_type",
            "type_oid",
            "type_schema",
            "type_name",
            "type_kind",
            "type_category",
            "domain_base_type",
            "domain_base_schema",
            "domain_base_name",
            "array_element_type",
            "array_element_schema",
            "array_element_name",
            "array_dimensions",
            "is_not_null",
            "has_default",
            "default_expr",
        }
    ),
    "constraints": frozenset(
        {
            "constraint_oid",
            "constraint_name",
            "constraint_type",
            "schema_name",
            "relation_oid",
            "relation_name",
            "foreign_relation_oid",
            "foreign_schema_name",
            "foreign_relation_name",
            "constrained_attnums",
            "referenced_attnums",
            "fk_on_update",
            "fk_on_delete",
            "fk_match_type",
            "constraint_def",
            "check_expr",
        }
    ),
    "indexes": frozenset(
        {
            "index_oid",
            "index_schema_name",
            "index_name",
            "relation_oid",
            "table_oid",
            "table_schema_name",
            "table_name",
            "index_tablespace_name",
            "access_method",
            "access_method_extension",
            "operator_classes",
            "operator_class_extensions",
            "is_unique",
            "is_primary",
            "is_valid",
            "predicate_expr",
            "index_def",
        }
    ),
    "pk_columns": frozenset(
        {
            "constraint_oid",
            "constraint_name",
            "schema_name",
            "relation_oid",
            "relation_name",
            "column_ordinal",
            "column_name",
        }
    ),
    "fk_edges": frozenset(
        {
            "fk_constraint_oid",
            "fk_constraint_name",
            "child_schema_name",
            "child_relation_oid",
            "child_relation_name",
            "parent_schema_name",
            "parent_relation_oid",
            "parent_relation_name",
            "column_ordinal",
            "child_column_name",
            "parent_column_name",
            "fk_on_update",
            "fk_on_delete",
            "fk_match_type",
        }
    ),
    "citus_distributed_tables": frozenset(
        {
            "relation_oid",
            "schema_name",
            "relation_name",
            "distribution_method",
            "distribution_key",
            "colocation_id",
            "replication_model",
            "configured_shard_count",
            "replication_factor",
            "shard_count",
        }
    ),
}

_DROP_PUBLIC_VALUE = object()


def _validate_public_export_mode(mode: str) -> None:
    """Keep paid live-LLM generation behind authenticated project routes."""
    if mode not in {"markdown", "llm-prompt"}:
        raise HTTPException(
            status_code=400,
            detail="unsupported public export mode",
        )


def _project_public_value(value: object) -> object:
    """Copy JSON scalar/list values while rejecting nested object payloads."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        projected_items = [_project_public_value(item) for item in value]
        return [item for item in projected_items if item is not _DROP_PUBLIC_VALUE]
    return _DROP_PUBLIC_VALUE


def _project_public_row(row: object, allowed_keys: frozenset[str]) -> object:
    if not isinstance(row, dict):
        return _DROP_PUBLIC_VALUE

    projected: dict[str, object] = {}
    for key, value in row.items():
        if not isinstance(key, str) or key not in allowed_keys:
            continue
        public_value = _project_public_value(value)
        if public_value is not _DROP_PUBLIC_VALUE:
            projected[key] = public_value
    return projected


def _redact_sensitive_snapshot_fields(data: object) -> dict[str, object]:
    """Project snapshot JSON onto the path-scoped public DTO v1."""
    if not isinstance(data, dict):
        return {}

    projected: dict[str, object] = {}
    for key in _PUBLIC_SNAPSHOT_V1_ROOT_KEYS:
        if key not in data:
            continue
        public_value = _project_public_value(data[key])
        if public_value is not _DROP_PUBLIC_VALUE:
            projected[key] = public_value

    for collection, allowed_keys in _PUBLIC_SNAPSHOT_V1_ROW_KEYS.items():
        rows = data.get(collection)
        if not isinstance(rows, list):
            continue
        projected_rows = [
            row
            if collection == "schemas" and isinstance(row, str)
            else _project_public_row(row, allowed_keys)
            for row in rows
        ]
        projected[collection] = [
            row for row in projected_rows if row is not _DROP_PUBLIC_VALUE
        ]

    return projected


def _redacted_snapshot_dict(
    snapshot_json: dict | list | str | int | float | bool | None,
) -> dict:
    """Return a snapshot dict with sensitive fields redacted for public export.

    Spec/DDL generators require a ``dict``; a non-dict payload degrades to an
    empty dict so a shared export can never leak raw comments/example values.
    """
    return _redact_sensitive_snapshot_fields(snapshot_json)


@router.post("/projects/{project_space_uuid}/share-links")
async def create_share_link(
    project_space_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Create a share link for a project (owner-only)."""
    # owner only
    row = await session.execute(
        select(ProjectMember.project_role).where(
            ProjectMember.project_space_uuid == project_space_uuid,
            ProjectMember.user_account_uuid == user.user_account_uuid,
        )
    )
    if row.scalar_one_or_none() != "owner":
        raise HTTPException(status_code=403, detail="owner role required")

    created_at = dt.datetime.now(dt.timezone.utc)
    expires_at = created_at + dt.timedelta(hours=settings.share_link_ttl_hours)
    link = ShareLink(
        share_link_uuid=uuid.uuid4(),
        project_space_uuid=project_space_uuid,
        created_by_user_uuid=user.user_account_uuid,
        permission_kind="viewer",
        expires_at=expires_at,
        created_at=created_at,
    )
    session.add(link)
    await session.commit()
    return {
        "share_link_uuid": str(link.share_link_uuid),
        "permission_kind": link.permission_kind,
        "url_path": f"/api/share/{link.share_link_uuid}",
        "expires_at": expires_at.isoformat(),
    }


@router.delete(
    "/projects/{project_space_uuid}/share-links/{share_link_uuid}",
    status_code=204,
)
async def revoke_share_link(
    project_space_uuid: uuid.UUID,
    share_link_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Revoke a project bearer link immediately (owner-only)."""
    row = await session.execute(
        select(ProjectMember.project_role).where(
            ProjectMember.project_space_uuid == project_space_uuid,
            ProjectMember.user_account_uuid == user.user_account_uuid,
        )
    )
    if row.scalar_one_or_none() != "owner":
        raise HTTPException(status_code=403, detail="owner role required")

    link = await session.get(ShareLink, share_link_uuid)
    if link is None or link.project_space_uuid != project_space_uuid:
        raise HTTPException(status_code=404, detail="share link not found")

    await session.delete(link)
    await session.commit()
    return Response(status_code=204)


@router.get("/share/{share_link_uuid}")
async def get_share_link_info(
    share_link_uuid: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return share metadata from the primary-consistent capability boundary."""
    link = await session.get(ShareLink, share_link_uuid)
    if link is None:
        raise HTTPException(status_code=404, detail="share link not found")
    if link.expires_at is not None and link.expires_at <= dt.datetime.now(
        dt.timezone.utc
    ):
        raise HTTPException(status_code=410, detail="share link expired")

    rows = await session.execute(
        select(SchemaSnapshot)
        .where(
            SchemaSnapshot.project_space_uuid == link.project_space_uuid,
            SchemaSnapshot.status == "succeeded",
        )
        .order_by(SchemaSnapshot.created_at.desc())
        .limit(20)
    )
    snaps = rows.scalars().all()
    return {
        "project_space_uuid": str(link.project_space_uuid),
        "permission_kind": link.permission_kind,
        "snapshots": [
            {
                "schema_snapshot_uuid": str(s.schema_snapshot_uuid),
                "status": s.status,
                "schema_filter": s.schema_filter,
                "created_at": s.created_at.isoformat(),
            }
            for s in snaps
            if s.status == "succeeded"
        ],
    }


@router.get("/share/{share_link_uuid}/snapshots/{schema_snapshot_uuid}")
async def get_shared_snapshot(
    share_link_uuid: uuid.UUID,
    schema_snapshot_uuid: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return a snapshot via a share link (no auth)."""
    link = await session.get(ShareLink, share_link_uuid)
    if link is None:
        raise HTTPException(status_code=404, detail="share link not found")
    if link.expires_at is not None and link.expires_at <= dt.datetime.now(
        dt.timezone.utc
    ):
        raise HTTPException(status_code=410, detail="share link expired")

    snap = await session.get(SchemaSnapshot, schema_snapshot_uuid)
    if (
        snap is None
        or snap.project_space_uuid != link.project_space_uuid
        or snap.status != "succeeded"
    ):
        raise HTTPException(status_code=404, detail="snapshot not found")

    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    return {
        "schema_snapshot_uuid": str(snap.schema_snapshot_uuid),
        "status": snap.status,
        "schema_filter": snap.schema_filter,
        "error_message": None,
        "snapshot_json": _redact_sensitive_snapshot_fields(data.snapshot_json)
        if data
        else None,
    }


@router.get(
    "/share/{share_link_uuid}/snapshots/{schema_snapshot_uuid}/export.sql",
    response_class=PlainTextResponse,
)
async def export_shared_snapshot_sql(
    share_link_uuid: uuid.UUID,
    schema_snapshot_uuid: uuid.UUID,
    dialect: str = Query("postgresql", pattern="^(postgresql|snowflake)$"),
    session: AsyncSession = Depends(get_session),
) -> str:
    """Export a shared snapshot as SQL via a share link."""
    link = await session.get(ShareLink, share_link_uuid)
    if link is None:
        raise HTTPException(status_code=404, detail="share link not found")
    if link.expires_at is not None and link.expires_at <= dt.datetime.now(
        dt.timezone.utc
    ):
        raise HTTPException(status_code=410, detail="share link expired")

    snap = await session.get(SchemaSnapshot, schema_snapshot_uuid)
    if (
        snap is None
        or snap.project_space_uuid != link.project_space_uuid
        or snap.status != "succeeded"
    ):
        raise HTTPException(status_code=404, detail="snapshot not found")

    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    if data is None:
        return "-- snapshot data not found\n"
    # Public share export: redact comments/example values so COMMENT ON / embedded
    # metadata never leave the share boundary.
    return snapshot_json_to_sql(
        _redacted_snapshot_dict(data.snapshot_json), target_dialect=dialect
    )


@router.get(
    "/share/{share_link_uuid}/snapshots/{schema_snapshot_uuid}/reversing-spec.md",
    response_class=PlainTextResponse,
)
async def export_shared_snapshot_reversing_spec(
    share_link_uuid: uuid.UUID,
    schema_snapshot_uuid: uuid.UUID,
    mode: str = Query("markdown", pattern="^(markdown|llm-prompt)$"),
    session: AsyncSession = Depends(get_session),
) -> str:
    """Export a shared snapshot as a DB reversing spec or LLM prompt."""
    _validate_public_export_mode(mode)
    link = await session.get(ShareLink, share_link_uuid)
    if link is None:
        raise HTTPException(status_code=404, detail="share link not found")
    if link.expires_at is not None and link.expires_at <= dt.datetime.now(
        dt.timezone.utc
    ):
        raise HTTPException(status_code=410, detail="share link expired")

    snap = await session.get(SchemaSnapshot, schema_snapshot_uuid)
    if (
        snap is None
        or snap.project_space_uuid != link.project_space_uuid
        or snap.status != "succeeded"
    ):
        raise HTTPException(status_code=404, detail="snapshot not found")

    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    if data is None:
        return "# DB Reversing Specification\n\nSnapshot data not found.\n"
    # Public share export: redact comments/example values (the reversing spec
    # otherwise embeds relation/column comments and example values verbatim).
    redacted_snapshot = _redacted_snapshot_dict(data.snapshot_json)
    return generate_reversing_spec(redacted_snapshot, mode=mode)


@router.get(
    "/share/{share_link_uuid}/snapshots/{schema_snapshot_uuid}/index-design.md",
    response_class=PlainTextResponse,
)
async def export_shared_snapshot_index_design(
    share_link_uuid: uuid.UUID,
    schema_snapshot_uuid: uuid.UUID,
    mode: str = Query("markdown", pattern="^(markdown|llm-prompt)$"),
    session: AsyncSession = Depends(get_session),
) -> str:
    """Export shared table/index design guidance or an LLM prompt."""
    _validate_public_export_mode(mode)
    link = await session.get(ShareLink, share_link_uuid)
    if link is None:
        raise HTTPException(status_code=404, detail="share link not found")
    if link.expires_at is not None and link.expires_at <= dt.datetime.now(
        dt.timezone.utc
    ):
        raise HTTPException(status_code=410, detail="share link expired")

    snap = await session.get(SchemaSnapshot, schema_snapshot_uuid)
    if (
        snap is None
        or snap.project_space_uuid != link.project_space_uuid
        or snap.status != "succeeded"
    ):
        raise HTTPException(status_code=404, detail="snapshot not found")

    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    if data is None:
        return "# ERD Index Design\n\nSnapshot data not found.\n"
    # Public share export: same redaction contract as reversing-spec / JSON share.
    redacted_snapshot = _redacted_snapshot_dict(data.snapshot_json)
    return generate_index_design_spec(redacted_snapshot, mode=mode)
