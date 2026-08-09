from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, Response
from sqlalchemy.exc import IntegrityError

from app.api.schema_models import (
    _validate_base_snapshot,
    create_schema_model,
    revise_schema_model,
)
from app.auth import CurrentUser
from app.models import SchemaModel, SchemaModelRevision
from app.schemas import SchemaModelCreateIn, SchemaModelReviseIn


def _user() -> CurrentUser:
    return CurrentUser(uuid.uuid4(), "test-user", "Test User")


def _model() -> dict:
    return {"format_version": 1, "postgresql_major": 18, "schemas": []}


class FakeWriteSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.get = AsyncMock()
        self.flush = AsyncMock()
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    def add(self, value: object) -> None:
        self.added.append(value)


@pytest.mark.parametrize(
    "snapshot",
    [
        None,
        SimpleNamespace(project_space_uuid=uuid.uuid4(), status="succeeded"),
        SimpleNamespace(project_space_uuid=None, status="running"),
    ],
)
@pytest.mark.asyncio
async def test_base_snapshot_must_exist_in_project_and_be_succeeded(
    snapshot: object | None,
) -> None:
    project_uuid = uuid.uuid4()
    if snapshot is not None and getattr(snapshot, "status") == "running":
        snapshot.project_space_uuid = project_uuid
    session = FakeWriteSession()
    session.get.return_value = snapshot

    with pytest.raises(HTTPException) as exc_info:
        await _validate_base_snapshot(session, project_uuid, uuid.uuid4())

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "base snapshot is not usable"


@pytest.mark.asyncio
async def test_base_snapshot_accepts_succeeded_snapshot_in_same_project() -> None:
    project_uuid = uuid.uuid4()
    session = FakeWriteSession()
    session.get.return_value = SimpleNamespace(
        project_space_uuid=project_uuid, status="succeeded"
    )

    await _validate_base_snapshot(session, project_uuid, uuid.uuid4())


@pytest.mark.asyncio
async def test_create_schema_model_persists_identity_and_immutable_revision() -> None:
    session = FakeWriteSession()
    project_uuid = uuid.uuid4()
    user = _user()
    response = Response()

    with patch(
        "app.api.schema_models.require_project_member", new_callable=AsyncMock
    ) as membership:
        out = await create_schema_model(
            project_space_uuid=project_uuid,
            body=SchemaModelCreateIn(model_name="Target schema", model_json=_model()),
            response=response,
            user=user,
            session=session,
        )

    membership.assert_awaited_once_with(
        session, project_uuid, user.user_account_uuid, minimum_role="editor"
    )
    identity = next(item for item in session.added if isinstance(item, SchemaModel))
    revision = next(
        item for item in session.added if isinstance(item, SchemaModelRevision)
    )
    assert identity.current_revision_number == 1
    assert revision.schema_model_uuid == identity.schema_model_uuid
    assert revision.revision_number == 1
    assert revision.model_json == _model()
    assert out.revision_digest == revision.revision_digest
    assert response.headers["etag"] == f'"{revision.schema_model_revision_uuid}"'
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_schema_model_returns_conflict_for_duplicate_name() -> None:
    session = FakeWriteSession()
    session.flush.side_effect = IntegrityError(
        "INSERT INTO schema_model", {}, RuntimeError("duplicate key")
    )

    with patch(
        "app.api.schema_models.require_project_member", new_callable=AsyncMock
    ):
        with pytest.raises(HTTPException) as exc_info:
            await create_schema_model(
                project_space_uuid=uuid.uuid4(),
                body=SchemaModelCreateIn(
                    model_name="Target schema", model_json=_model()
                ),
                response=Response(),
                user=_user(),
                session=session,
            )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "schema model name already exists"
    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_revise_schema_model_rejects_stale_if_match() -> None:
    identity = SimpleNamespace(
        schema_model_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        model_name="Target schema",
        current_revision_number=2,
    )
    current = SimpleNamespace(
        schema_model_revision_uuid=uuid.uuid4(), revision_digest="a" * 64
    )
    session = FakeWriteSession()

    with patch(
        "app.api.schema_models._get_model_for_update",
        new=AsyncMock(return_value=(identity, current)),
    ), patch(
        "app.api.schema_models.require_project_member", new_callable=AsyncMock
    ):
        with pytest.raises(HTTPException) as exc_info:
            await revise_schema_model(
                schema_model_uuid=identity.schema_model_uuid,
                body=SchemaModelReviseIn(model_json=_model()),
                response=Response(),
                if_match='"' + "b" * 64 + '"',
                user=_user(),
                session=session,
            )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "schema model revision is stale"
    assert session.added == []


@pytest.mark.asyncio
async def test_revise_schema_model_uses_revision_uuid_when_base_only_revision_changes() -> None:
    from app.forward.schema_model import schema_model_digest

    model_json = _model()
    shared_model_digest = schema_model_digest(model_json)
    identity = SimpleNamespace(
        schema_model_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        model_name="Target schema",
        current_revision_number=3,
        updated_at=None,
    )
    current = SimpleNamespace(
        schema_model_revision_uuid=uuid.uuid4(),
        revision_number=3,
        revision_digest=shared_model_digest,
        model_json=model_json,
        base_schema_snapshot_uuid=uuid.uuid4(),
    )

    session = FakeWriteSession()
    response = Response()
    with patch(
        "app.api.schema_models._get_model_for_update",
        new=AsyncMock(return_value=(identity, current)),
    ), patch(
        "app.api.schema_models.require_project_member", new_callable=AsyncMock
    ):
        out = await revise_schema_model(
            schema_model_uuid=identity.schema_model_uuid,
            body=SchemaModelReviseIn(
                model_json=model_json, base_schema_snapshot_uuid=None
            ),
            response=response,
            if_match=f'"{current.schema_model_revision_uuid}"',
            user=_user(),
            session=session,
        )

    assert out.revision_number == 4
    revision = next(
        item for item in session.added if isinstance(item, SchemaModelRevision)
    )
    assert revision.base_schema_snapshot_uuid is None
    assert response.headers["etag"] == f'"{revision.schema_model_revision_uuid}"'


@pytest.mark.asyncio
async def test_revise_schema_model_rejects_weak_if_match() -> None:
    identity = SimpleNamespace(
        schema_model_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        model_name="Target schema",
        current_revision_number=2,
    )
    current = SimpleNamespace(
        schema_model_revision_uuid=uuid.uuid4(), revision_digest="a" * 64
    )

    with patch(
        "app.api.schema_models._get_model_for_update",
        new=AsyncMock(return_value=(identity, current)),
    ), patch(
        "app.api.schema_models.require_project_member", new_callable=AsyncMock
    ):
        with pytest.raises(HTTPException) as exc_info:
            await revise_schema_model(
                schema_model_uuid=identity.schema_model_uuid,
                body=SchemaModelReviseIn(model_json=_model()),
                response=Response(),
                if_match=f'W/"{current.schema_model_revision_uuid}"',
                user=_user(),
                session=FakeWriteSession(),
            )

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_revise_schema_model_creates_next_revision() -> None:
    identity = SimpleNamespace(
        schema_model_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        model_name="Target schema",
        current_revision_number=2,
        updated_at=None,
    )
    current = SimpleNamespace(
        schema_model_revision_uuid=uuid.uuid4(), revision_digest="a" * 64
    )
    session = FakeWriteSession()
    user = _user()
    response = Response()

    with patch(
        "app.api.schema_models._get_model_for_update",
        new=AsyncMock(return_value=(identity, current)),
    ), patch(
        "app.api.schema_models.require_project_member", new_callable=AsyncMock
    ) as membership:
        out = await revise_schema_model(
            schema_model_uuid=identity.schema_model_uuid,
            body=SchemaModelReviseIn(model_json=_model()),
            response=response,
            if_match=f'"{current.schema_model_revision_uuid}"',
            user=user,
            session=session,
        )

    membership.assert_awaited_once_with(
        session,
        identity.project_space_uuid,
        user.user_account_uuid,
        minimum_role="editor",
    )
    revision = next(
        item for item in session.added if isinstance(item, SchemaModelRevision)
    )
    assert revision.revision_number == 3
    assert identity.current_revision_number == 3
    assert out.revision_number == 3
    assert response.headers["etag"] == f'"{revision.schema_model_revision_uuid}"'
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_revise_schema_model_is_idempotent_for_identical_revision() -> None:
    model_json = _model()
    identity = SimpleNamespace(
        schema_model_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        model_name="Target schema",
        current_revision_number=2,
        updated_at=None,
    )
    current = SimpleNamespace(
        schema_model_revision_uuid=uuid.uuid4(),
        revision_number=2,
        revision_digest="placeholder",
        model_json=model_json,
        base_schema_snapshot_uuid=None,
    )
    from app.forward.schema_model import schema_model_digest

    current.revision_digest = schema_model_digest(model_json)
    session = FakeWriteSession()

    with patch(
        "app.api.schema_models._get_model_for_update",
        new=AsyncMock(return_value=(identity, current)),
    ), patch(
        "app.api.schema_models.require_project_member", new_callable=AsyncMock
    ):
        out = await revise_schema_model(
            schema_model_uuid=identity.schema_model_uuid,
            body=SchemaModelReviseIn(model_json=model_json),
            response=Response(),
            if_match=f'"{current.schema_model_revision_uuid}"',
            user=_user(),
            session=session,
        )

    assert out.revision_number == 2
    assert session.added == []
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_revise_schema_model_masks_non_member_as_not_found() -> None:
    identity = SimpleNamespace(
        schema_model_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        model_name="Target schema",
        current_revision_number=2,
    )
    current = SimpleNamespace(revision_digest="a" * 64)
    denied = HTTPException(status_code=403, detail="project access denied")

    with patch(
        "app.api.schema_models._get_model_for_update",
        new=AsyncMock(return_value=(identity, current)),
    ), patch(
        "app.api.schema_models.require_project_member",
        new=AsyncMock(side_effect=denied),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await revise_schema_model(
                schema_model_uuid=identity.schema_model_uuid,
                body=SchemaModelReviseIn(model_json=_model()),
                response=Response(),
                if_match=current.revision_digest,
                user=_user(),
                session=FakeWriteSession(),
            )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "schema model not found"
