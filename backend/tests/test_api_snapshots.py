import uuid
import pytest
from fastapi import HTTPException
from unittest.mock import AsyncMock, patch
from app.api.snapshots import create_snapshot
from app.schemas import SnapshotCreateIn
from app.auth import CurrentUser
from app.models import DbConnection

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
