import uuid
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, call, patch
from app.api.snapshots import create_snapshot, get_snapshot
from app.schemas import SnapshotCreateIn
from app.auth import CurrentUser
from app.models import DbConnection, SchemaSnapshot, SchemaSnapshotData


def _user() -> CurrentUser:
    return CurrentUser(
        user_account_uuid=uuid.uuid4(), subject="test", display_name="Test"
    )


@pytest.mark.asyncio
async def test_create_snapshot_rejects_invalid_connection_uuid():
    # Setup mocks
    session_mock = AsyncMock()
    session_mock.get.return_value = None

    project_space_uuid = uuid.uuid4()
    body = SnapshotCreateIn(db_connection_uuid=uuid.uuid4(), schema_filter=None)
    user = CurrentUser(user_account_uuid=uuid.uuid4(), subject="test", display_name="Test")

    with patch("app.api.snapshots.require_project_member", new_callable=AsyncMock):
        with pytest.raises(HTTPException) as exc_info:
            await create_snapshot(
                project_space_uuid=project_space_uuid,
                body=body,
                user=user,
                session=session_mock
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "connection not found"


@pytest.mark.asyncio
async def test_get_snapshot_returns_not_found_without_reading_data_when_unauthorized():
    session_mock = AsyncMock()
    snapshot_id = uuid.uuid4()
    project_space_uuid = uuid.uuid4()
    user = _user()
    session_mock.scalar.return_value = project_space_uuid
    require_member = AsyncMock(side_effect=HTTPException(status_code=403))

    with patch("app.api.snapshots.require_project_member", require_member):
        out = await get_snapshot(
            schema_snapshot_uuid=snapshot_id,
            user=user,
            session=session_mock,
        )

    assert out.schema_snapshot_uuid == snapshot_id
    assert out.status == "not_found"
    assert out.snapshot_json is None
    require_member.assert_awaited_once_with(
        session_mock, project_space_uuid, user.user_account_uuid
    )
    session_mock.get.assert_not_called()


@pytest.mark.asyncio
async def test_get_snapshot_reads_data_only_after_project_membership():
    session_mock = AsyncMock()
    snapshot_id = uuid.uuid4()
    project_space_uuid = uuid.uuid4()
    user = _user()
    session_mock.scalar.return_value = project_space_uuid
    snapshot_json = {"relations": []}
    session_mock.get.side_effect = [
        SimpleNamespace(
            schema_snapshot_uuid=snapshot_id,
            status="ready",
            schema_filter="public",
            error_message=None,
        ),
        SimpleNamespace(snapshot_json=snapshot_json),
    ]
    require_member = AsyncMock()

    with patch("app.api.snapshots.require_project_member", require_member):
        out = await get_snapshot(
            schema_snapshot_uuid=snapshot_id,
            user=user,
            session=session_mock,
        )

    assert out.schema_snapshot_uuid == snapshot_id
    assert out.status == "ready"
    assert out.schema_filter == "public"
    assert out.error_message is None
    assert out.snapshot_json == snapshot_json
    require_member.assert_awaited_once_with(
        session_mock, project_space_uuid, user.user_account_uuid
    )
    assert session_mock.get.await_args_list == [
        call(SchemaSnapshot, snapshot_id),
        call(SchemaSnapshotData, snapshot_id),
    ]

@pytest.mark.asyncio
async def test_create_snapshot_rejects_connection_from_other_project():
    session_mock = AsyncMock()

    conn_mock = DbConnection(
        db_connection_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(), # Different project
        conn_name="test",
        dsn_ciphertext=b"x",
        dsn_nonce=b"x"
    )
    session_mock.get.return_value = conn_mock

    project_space_uuid = uuid.uuid4()
    body = SnapshotCreateIn(db_connection_uuid=conn_mock.db_connection_uuid, schema_filter=None)
    user = CurrentUser(user_account_uuid=uuid.uuid4(), subject="test", display_name="Test")

    with patch("app.api.snapshots.require_project_member", new_callable=AsyncMock):
        with pytest.raises(HTTPException) as exc_info:
            await create_snapshot(
                project_space_uuid=project_space_uuid,
                body=body,
                user=user,
                session=session_mock
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "connection not found"
