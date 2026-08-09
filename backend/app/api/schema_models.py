"""Versioned editable-schema API for server-authoritative forward engineering."""

from __future__ import annotations

import datetime as dt
import json
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.db import get_read_session, get_session
from app.forward.schema_model import (
    SchemaModelValidationError,
    canonicalize_schema_model,
    schema_model_digest,
)
from app.models import SchemaModel, SchemaModelRevision, SchemaSnapshot
from app.permissions import require_project_member
from app.sanitize import sanitize_for_storage
from app.schemas import (
    SchemaModelCreateIn,
    SchemaModelDetailOut,
    SchemaModelReviseIn,
)

router = APIRouter(prefix="/api/schema-models", tags=["schema-models"])
MAX_MODEL_BYTES = 2 * 1024 * 1024


def _canonical_model(model_json: dict) -> dict:
    """Validate size and return canonical JSON, translating errors to 422."""

    if len(json.dumps(model_json, ensure_ascii=False).encode("utf-8")) > MAX_MODEL_BYTES:
        raise HTTPException(status_code=413, detail="schema model payload too large")
    try:
        return canonicalize_schema_model(model_json)
    except SchemaModelValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


async def _validate_base_snapshot(
    session: AsyncSession,
    project_space_uuid: uuid.UUID,
    schema_snapshot_uuid: uuid.UUID | None,
) -> None:
    if schema_snapshot_uuid is None:
        return
    snapshot = await session.get(SchemaSnapshot, schema_snapshot_uuid)
    if (
        snapshot is None
        or snapshot.project_space_uuid != project_space_uuid
        or snapshot.status != "succeeded"
    ):
        raise HTTPException(status_code=422, detail="base snapshot is not usable")


def _detail(model: SchemaModel, revision: SchemaModelRevision) -> SchemaModelDetailOut:
    return SchemaModelDetailOut(
        schema_model_uuid=model.schema_model_uuid,
        model_name=model.model_name,
        schema_model_revision_uuid=revision.schema_model_revision_uuid,
        revision_number=revision.revision_number,
        revision_digest=revision.revision_digest,
        model_json=revision.model_json,
        base_schema_snapshot_uuid=revision.base_schema_snapshot_uuid,
    )


async def _get_model_for_update(
    session: AsyncSession, schema_model_uuid: uuid.UUID
) -> tuple[SchemaModel, SchemaModelRevision] | None:
    model = await session.get(SchemaModel, schema_model_uuid, with_for_update=True)
    if model is None:
        return None
    revision = (
        await session.execute(
            select(SchemaModelRevision).where(
                SchemaModelRevision.schema_model_uuid == schema_model_uuid,
                SchemaModelRevision.revision_number == model.current_revision_number,
            )
        )
    ).scalar_one()
    return model, revision


def _revision_etag(revision: SchemaModelRevision) -> str:
    """Return a strong entity tag that identifies the complete revision row."""

    return f'"{revision.schema_model_revision_uuid}"'


@router.post("/by-project/{project_space_uuid}", response_model=SchemaModelDetailOut)
async def create_schema_model(
    project_space_uuid: uuid.UUID,
    body: SchemaModelCreateIn,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SchemaModelDetailOut:
    """Create a model identity and revision one in one database transaction."""

    await require_project_member(
        session, project_space_uuid, user.user_account_uuid, minimum_role="editor"
    )
    canonical = _canonical_model(body.model_json)
    await _validate_base_snapshot(
        session, project_space_uuid, body.base_schema_snapshot_uuid
    )
    now = dt.datetime.now(dt.timezone.utc)
    model = SchemaModel(
        schema_model_uuid=uuid.uuid4(),
        project_space_uuid=project_space_uuid,
        model_name=str(sanitize_for_storage(body.model_name)),
        current_revision_number=1,
        created_by_user_uuid=user.user_account_uuid,
        created_at=now,
        updated_at=now,
    )
    revision = SchemaModelRevision(
        schema_model_revision_uuid=uuid.uuid4(),
        schema_model_uuid=model.schema_model_uuid,
        revision_number=1,
        revision_digest=schema_model_digest(canonical),
        model_json=canonical,
        base_schema_snapshot_uuid=body.base_schema_snapshot_uuid,
        created_by_user_uuid=user.user_account_uuid,
        created_at=now,
    )
    session.add(model)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="schema model name already exists"
        ) from exc
    session.add(revision)
    await session.commit()
    response.headers["ETag"] = _revision_etag(revision)
    return _detail(model, revision)


@router.put("/{schema_model_uuid}", response_model=SchemaModelDetailOut)
async def revise_schema_model(
    schema_model_uuid: uuid.UUID,
    body: SchemaModelReviseIn,
    response: Response,
    if_match: str = Header(alias="If-Match"),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SchemaModelDetailOut:
    """Append a revision iff ``If-Match`` names the locked current digest."""

    found = await _get_model_for_update(session, schema_model_uuid)
    if found is None:
        raise HTTPException(status_code=404, detail="schema model not found")
    model, current = found
    try:
        await require_project_member(
            session,
            model.project_space_uuid,
            user.user_account_uuid,
            minimum_role="editor",
        )
    except HTTPException as exc:
        if exc.status_code == 403:
            raise HTTPException(status_code=404, detail="schema model not found") from exc
        raise
    if if_match.strip() != _revision_etag(current):
        raise HTTPException(status_code=409, detail="schema model revision is stale")
    canonical = _canonical_model(body.model_json)
    await _validate_base_snapshot(
        session, model.project_space_uuid, body.base_schema_snapshot_uuid
    )
    revision_digest = schema_model_digest(canonical)
    if (
        revision_digest == current.revision_digest
        and body.base_schema_snapshot_uuid == current.base_schema_snapshot_uuid
    ):
        response.headers["ETag"] = _revision_etag(current)
        return _detail(model, current)
    now = dt.datetime.now(dt.timezone.utc)
    revision = SchemaModelRevision(
        schema_model_revision_uuid=uuid.uuid4(),
        schema_model_uuid=model.schema_model_uuid,
        revision_number=model.current_revision_number + 1,
        revision_digest=revision_digest,
        model_json=canonical,
        base_schema_snapshot_uuid=body.base_schema_snapshot_uuid,
        created_by_user_uuid=user.user_account_uuid,
        created_at=now,
    )
    model.current_revision_number = revision.revision_number
    model.updated_at = now
    session.add(revision)
    await session.commit()
    response.headers["ETag"] = _revision_etag(revision)
    return _detail(model, revision)


@router.get("/{schema_model_uuid}", response_model=SchemaModelDetailOut)
async def get_schema_model(
    schema_model_uuid: uuid.UUID,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> SchemaModelDetailOut:
    """Return the current immutable revision, masking unauthorized identities."""

    model = await session.get(SchemaModel, schema_model_uuid)
    if model is None:
        raise HTTPException(status_code=404, detail="schema model not found")
    try:
        await require_project_member(
            session, model.project_space_uuid, user.user_account_uuid
        )
    except HTTPException as exc:
        if exc.status_code == 403:
            raise HTTPException(status_code=404, detail="schema model not found") from exc
        raise
    revision = (
        await session.execute(
            select(SchemaModelRevision).where(
                SchemaModelRevision.schema_model_uuid == schema_model_uuid,
                SchemaModelRevision.revision_number == model.current_revision_number,
            )
        )
    ).scalar_one()
    response.headers["ETag"] = _revision_etag(revision)
    return _detail(model, revision)
