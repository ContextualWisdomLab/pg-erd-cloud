from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth import CurrentUser, get_current_user
from app.db import get_session
from app.main import app
from app.models import UserAccount
from app.settings import settings

client = TestClient(app)


class MockAsyncSession:
    def __init__(self, db_user: UserAccount | None = None) -> None:
        self.db_user = db_user

    async def get(self, model, ident):
        return self.db_user

    def begin(self):
        class ContextManager:
            async def __aenter__(self):
                pass

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        return ContextManager()


def test_get_me_unauthenticated(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides = {}
    monkeypatch.setattr(settings, "oidc_issuer", "https://example.com")

    response = client.get("/api/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "missing bearer token"}


def test_get_me_authenticated(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides = {}
    user_uuid = uuid.uuid4()
    mock_user = CurrentUser(
        user_account_uuid=user_uuid,
        subject="test-subject",
        display_name="Test User",
    )

    async def override_get_current_user() -> CurrentUser:
        return mock_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        response = client.get("/api/me")
        assert response.status_code == 200
        data = response.json()
        assert data["user_account_uuid"] == str(user_uuid)
        assert data["subject"] == "test-subject"
        assert data["display_name"] == "Test User"
    finally:
        app.dependency_overrides.clear()


def test_patch_me_unauthenticated(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides = {}
    monkeypatch.setattr(settings, "oidc_issuer", "https://example.com")

    # Needs CSRF token bypass or just mock get_current_user instead, wait no, unauthenticated 401 should trigger before CSRF 403
    # Actually wait, CSRF middleware might be earlier
    response = client.patch("/api/me", json={"display_name": "New Name"})

    # Let's bypass csrf
    if response.status_code == 403:  # Csrf blocked it
        from app.csrf import generate_csrf_token
        from app.settings import settings as real_settings

        token = generate_csrf_token(real_settings.app_secret)
        response = client.patch(
            "/api/me",
            json={"display_name": "New Name"},
            headers={"X-CSRF-Token": token},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "missing bearer token"}


def test_patch_me_authenticated(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides = {}
    user_uuid = uuid.uuid4()
    mock_user = CurrentUser(
        user_account_uuid=user_uuid,
        subject="test-subject",
        display_name="Test User",
    )

    async def override_get_current_user() -> CurrentUser:
        return mock_user

    db_user = UserAccount(
        user_account_uuid=user_uuid,
        oidc_subject="test-subject",
        display_name="Test User",
    )

    async def override_get_session():
        yield MockAsyncSession(db_user=db_user)

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_session] = override_get_session

    try:
        from app.csrf import generate_csrf_token
        from app.settings import settings as real_settings

        token = generate_csrf_token(real_settings.app_secret)

        response = client.patch(
            "/api/me",
            json={"display_name": "New Name"},
            headers={"X-CSRF-Token": token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_account_uuid"] == str(user_uuid)
        assert data["subject"] == "test-subject"
        assert data["display_name"] == "New Name"

        assert db_user.display_name == "New Name"
    finally:
        app.dependency_overrides.clear()


def test_patch_me_authenticated_user_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides = {}
    user_uuid = uuid.uuid4()
    mock_user = CurrentUser(
        user_account_uuid=user_uuid,
        subject="test-subject",
        display_name="Test User",
    )

    async def override_get_current_user() -> CurrentUser:
        return mock_user

    async def override_get_session():
        yield MockAsyncSession(db_user=None)

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_session] = override_get_session

    try:
        from app.csrf import generate_csrf_token
        from app.settings import settings as real_settings

        token = generate_csrf_token(real_settings.app_secret)

        response = client.patch(
            "/api/me",
            json={"display_name": "New Name"},
            headers={"X-CSRF-Token": token},
        )
        assert response.status_code == 200
        # Check that display_name is the updated one even though db_user was None,
        # Or wait, what does the implementation do?
        # If not db_user, it falls back to the update_data if present
        data = response.json()
        assert data["display_name"] == "New Name"
    finally:
        app.dependency_overrides.clear()
