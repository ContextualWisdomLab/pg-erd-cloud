from __future__ import annotations

import uuid
import datetime as dt

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.connections import router
from app.auth import CurrentUser, get_current_user
from app.db import get_read_session, get_session
from app.models import DbConnection
from app.security import EncryptedBlob

app = FastAPI()
app.include_router(router)


class FakeScalars:
    def __init__(self, data):
        self.data = data

    def all(self):
        return self.data


class FakeResult:
    def __init__(self, data):
        self.data = data

    def scalars(self):
        return FakeScalars(self.data)

    def scalar_one_or_none(self):
        return self.data[0] if self.data else None


class FakeSession:
    def __init__(self, execute_result=None):
        self.execute_result = execute_result or []
        self.added = []

    async def execute(self, stmt, *args, **kwargs):
        return FakeResult(self.execute_result)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass


def fake_get_current_user():
    return CurrentUser(
        user_account_uuid=uuid.uuid4(), subject="test_user", display_name=None
    )


app.dependency_overrides[get_current_user] = fake_get_current_user


def test_list_connections_success(monkeypatch: pytest.MonkeyPatch):
    async def mock_require(*args, **kwargs):
        return "viewer"

    monkeypatch.setattr("app.api.connections.require_project_member", mock_require)

    fake_conn = DbConnection(
        db_connection_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        conn_name="Test Conn",
        dsn_ciphertext=b"enc",
        dsn_nonce=b"nonce",
        created_at=dt.datetime.now(dt.timezone.utc),
        updated_at=dt.datetime.now(dt.timezone.utc),
    )

    def fake_get_read_session():
        return FakeSession([fake_conn])

    app.dependency_overrides[get_read_session] = fake_get_read_session

    client = TestClient(app)
    response = client.get(f"/api/connections/by-project/{fake_conn.project_space_uuid}")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["conn_name"] == "Test Conn"
    assert data[0]["db_connection_uuid"] == str(fake_conn.db_connection_uuid)


def test_list_connections_access_denied(monkeypatch: pytest.MonkeyPatch):
    async def mock_require(*args, **kwargs):
        raise HTTPException(status_code=403, detail="project access denied")

    monkeypatch.setattr("app.api.connections.require_project_member", mock_require)

    def fake_get_read_session():
        return FakeSession([])

    app.dependency_overrides[get_read_session] = fake_get_read_session

    client = TestClient(app)
    response = client.get(f"/api/connections/by-project/{uuid.uuid4()}")

    assert response.status_code == 403
    assert response.json()["detail"] == "project access denied"


def test_create_connection_success(monkeypatch: pytest.MonkeyPatch):
    async def mock_require(*args, **kwargs):
        return "editor"

    monkeypatch.setattr("app.api.connections.require_project_member", mock_require)

    def mock_encrypt(text: str):
        return EncryptedBlob(ciphertext=b"encrypted_dsn", nonce=b"nonce")

    monkeypatch.setattr("app.api.connections.encrypt_text", mock_encrypt)

    session = FakeSession()

    def fake_get_session():
        return session

    app.dependency_overrides[get_session] = fake_get_session

    client = TestClient(app)
    project_uuid = uuid.uuid4()
    response = client.post(
        f"/api/connections/by-project/{project_uuid}",
        json={"conn_name": "New Conn", "dsn": "postgresql://test"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["conn_name"] == "New Conn"
    assert "db_connection_uuid" in data

    # Verify the object was added to session
    assert len(session.added) == 1
    added_obj = session.added[0]
    assert added_obj.conn_name == "New Conn"
    assert added_obj.dsn_ciphertext == b"encrypted_dsn"
    assert added_obj.project_space_uuid == project_uuid


def test_create_connection_access_denied(monkeypatch: pytest.MonkeyPatch):
    async def mock_require(*args, **kwargs):
        raise HTTPException(status_code=403, detail="insufficient project role")

    monkeypatch.setattr("app.api.connections.require_project_member", mock_require)

    def fake_get_session():
        return FakeSession()

    app.dependency_overrides[get_session] = fake_get_session

    client = TestClient(app)
    response = client.post(
        f"/api/connections/by-project/{uuid.uuid4()}",
        json={"conn_name": "New Conn", "dsn": "postgresql://test"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "insufficient project role"


def test_create_connection_invalid_payload():
    client = TestClient(app)
    response = client.post(
        f"/api/connections/by-project/{uuid.uuid4()}",
        json={"conn_name": "New Conn"},  # missing dsn
    )

    assert response.status_code == 422
