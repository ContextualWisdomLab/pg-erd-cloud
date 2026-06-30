from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.me import router as me_router
from app.auth import CurrentUser, get_current_user
from app.db import get_session
from app.models import UserAccount


def get_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(me_router)
    return app


def test_get_me() -> None:
    app = get_test_app()
    test_user = CurrentUser(
        user_account_uuid=uuid.uuid4(),
        subject="test-subject",
        display_name="Test User",
    )

    app.dependency_overrides[get_current_user] = lambda: test_user

    with TestClient(app) as client:
        response = client.get("/api/me")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["user_account_uuid"] == str(test_user.user_account_uuid)
    assert data["subject"] == test_user.subject
    assert data["display_name"] == test_user.display_name


class MockSession:
    def __init__(self, user_account: UserAccount | None = None):
        self.user_account = user_account
        self.committed = False

    async def execute(self, stmt):
        class MockResult:
            def __init__(self, row):
                self.row = row

            def scalar_one_or_none(self):
                return self.row

        return MockResult(self.user_account)

    async def commit(self):
        self.committed = True


def test_patch_me() -> None:
    app = get_test_app()
    user_uuid = uuid.uuid4()
    test_user = CurrentUser(
        user_account_uuid=user_uuid,
        subject="test-subject",
        display_name="Test User",
    )

    db_user = UserAccount(
        user_account_uuid=user_uuid,
        oidc_subject="test-subject",
        display_name="Test User",
    )

    mock_session = MockSession(user_account=db_user)

    async def get_mock_session() -> AsyncIterator[MockSession]:
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_session] = get_mock_session

    with TestClient(app) as client:
        response = client.patch("/api/me", json={"display_name": "New Name"})

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["user_account_uuid"] == str(user_uuid)
    assert data["subject"] == "test-subject"
    assert data["display_name"] == "New Name"
    assert mock_session.committed is True
    assert db_user.display_name == "New Name"


def test_patch_me_user_not_found() -> None:
    app = get_test_app()
    user_uuid = uuid.uuid4()
    test_user = CurrentUser(
        user_account_uuid=user_uuid,
        subject="test-subject",
        display_name="Test User",
    )

    mock_session = MockSession(user_account=None)

    async def get_mock_session() -> AsyncIterator[MockSession]:
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_session] = get_mock_session

    with TestClient(app) as client:
        response = client.patch("/api/me", json={"display_name": "New Name"})

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"
    assert mock_session.committed is False
