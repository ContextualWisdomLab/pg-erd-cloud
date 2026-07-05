from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.db import get_read_session, get_session
from app.ddl.export import snapshot_json_to_sql
from app.models import (
    ProjectMember,
    SchemaSnapshot,
    SchemaSnapshotData,
    ShareLink,
)
from app.redact import redact_sensitive_schema_data
from app.spec.llm import (
    LlmConfigurationError,
    LlmProviderError,
    generate_index_design_llm_draft,
    generate_reversing_llm_draft,
)
from app.spec.index_design import generate_index_design_spec
from app.spec.reversing import generate_reversing_spec

router = APIRouter(prefix="/api", tags=["share"])


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

    link = ShareLink(
        share_link_uuid=uuid.uuid4(),
        project_space_uuid=project_space_uuid,
        created_by_user_uuid=user.user_account_uuid,
        permission_kind="viewer",
        expires_at=None,
        created_at=dt.datetime.now(dt.timezone.utc),
    )
    session.add(link)
    await session.commit()
    return {
        "share_link_uuid": str(link.share_link_uuid),
        "permission_kind": link.permission_kind,
        "url_path": f"/api/share/{link.share_link_uuid}",
    }


@router.get("/share/{share_link_uuid}")
async def get_share_link_info(
    share_link_uuid: uuid.UUID,
    session: AsyncSession = Depends(get_read_session),
) -> dict:
    """Return share link metadata and recent snapshots."""
    link = await session.get(ShareLink, share_link_uuid)
    if link is None:
        raise HTTPException(status_code=404, detail="share link not found")
    if link.expires_at is not None and link.expires_at <= dt.datetime.now(
        dt.timezone.utc
    ):
        raise HTTPException(status_code=410, detail="share link expired")

    rows = await session.execute(
        select(SchemaSnapshot)
        .where(SchemaSnapshot.project_space_uuid == link.project_space_uuid)
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
        ],
    }


@router.get("/share/{share_link_uuid}/snapshots/{schema_snapshot_uuid}")
async def get_shared_snapshot(
    share_link_uuid: uuid.UUID,
    schema_snapshot_uuid: uuid.UUID,
    session: AsyncSession = Depends(get_read_session),
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
    if snap is None or snap.project_space_uuid != link.project_space_uuid:
        raise HTTPException(status_code=404, detail="snapshot not found")

    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    return {
        "schema_snapshot_uuid": str(snap.schema_snapshot_uuid),
        "status": snap.status,
        "schema_filter": snap.schema_filter,
        "error_message": snap.error_message,
        "snapshot_json": redact_sensitive_schema_data(data.snapshot_json) if data else None,
    }


@router.get(
    "/share/{share_link_uuid}/snapshots/{schema_snapshot_uuid}/export.sql",
    response_class=PlainTextResponse,
)
async def export_shared_snapshot_sql(
    share_link_uuid: uuid.UUID,
    schema_snapshot_uuid: uuid.UUID,
    dialect: str = Query("postgresql", pattern="^(postgresql|snowflake)$"),
    session: AsyncSession = Depends(get_read_session),
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
    if snap is None or snap.project_space_uuid != link.project_space_uuid:
        raise HTTPException(status_code=404, detail="snapshot not found")

    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    if data is None:
        return "-- snapshot data not found\n"

    redacted_json = redact_sensitive_schema_data(data.snapshot_json)
    return snapshot_json_to_sql(redacted_json, target_dialect=dialect)


@router.get(
    "/share/{share_link_uuid}/snapshots/{schema_snapshot_uuid}/reversing-spec.md",
    response_class=PlainTextResponse,
)
async def export_shared_snapshot_reversing_spec(
    share_link_uuid: uuid.UUID,
    schema_snapshot_uuid: uuid.UUID,
    mode: str = Query("markdown", pattern="^(markdown|llm-prompt|llm-draft)$"),
    session: AsyncSession = Depends(get_read_session),
) -> str:
    """Export a shared snapshot as a DB reversing spec or LLM prompt."""
    link = await session.get(ShareLink, share_link_uuid)
    if link is None:
        raise HTTPException(status_code=404, detail="share link not found")
    if link.expires_at is not None and link.expires_at <= dt.datetime.now(
        dt.timezone.utc
    ):
        raise HTTPException(status_code=410, detail="share link expired")

    snap = await session.get(SchemaSnapshot, schema_snapshot_uuid)
    if snap is None or snap.project_space_uuid != link.project_space_uuid:
        raise HTTPException(status_code=404, detail="snapshot not found")

    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    if data is None:
        return "# DB Reversing Specification\n\nSnapshot data not found.\n"

    redacted_json = redact_sensitive_schema_data(data.snapshot_json)
    if mode == "llm-draft":
        try:
            return await generate_reversing_llm_draft(redacted_json)
        except LlmConfigurationError as exc:
            raise HTTPException(
                status_code=503, detail="LLM configuration error"
            ) from exc
        except LlmProviderError as exc:
            raise HTTPException(
                status_code=502, detail="LLM provider request failed"
            ) from exc
    return generate_reversing_spec(redacted_json, mode=mode)


@router.get(
    "/share/{share_link_uuid}/snapshots/{schema_snapshot_uuid}/index-design.md",
    response_class=PlainTextResponse,
)
async def export_shared_snapshot_index_design(
    share_link_uuid: uuid.UUID,
    schema_snapshot_uuid: uuid.UUID,
    mode: str = Query("markdown", pattern="^(markdown|llm-prompt|llm-draft)$"),
    session: AsyncSession = Depends(get_read_session),
) -> str:
    """Export shared table/index design guidance or an LLM prompt."""
    link = await session.get(ShareLink, share_link_uuid)
    if link is None:
        raise HTTPException(status_code=404, detail="share link not found")
    if link.expires_at is not None and link.expires_at <= dt.datetime.now(
        dt.timezone.utc
    ):
        raise HTTPException(status_code=410, detail="share link expired")

    snap = await session.get(SchemaSnapshot, schema_snapshot_uuid)
    if snap is None or snap.project_space_uuid != link.project_space_uuid:
        raise HTTPException(status_code=404, detail="snapshot not found")

    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    if data is None:
        return "# ERD Index Design\n\nSnapshot data not found.\n"

    redacted_json = redact_sensitive_schema_data(data.snapshot_json)
    if mode == "llm-draft":
        try:
            return await generate_index_design_llm_draft(redacted_json)
        except LlmConfigurationError as exc:
            raise HTTPException(
                status_code=503, detail="LLM configuration error"
            ) from exc
        except LlmProviderError as exc:
            raise HTTPException(
                status_code=502, detail="LLM provider request failed"
            ) from exc
    return generate_index_design_spec(redacted_json, mode=mode)
