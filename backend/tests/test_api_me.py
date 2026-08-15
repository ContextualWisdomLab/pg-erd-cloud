"""Integration tests for the authenticated current-user endpoint."""

from __future__ import annotations

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.api.me import router
from app.auth import CurrentUser, get_current_user


@pytest.mark.parametrize("display_name", ["Test User", None])
def test_get_me_returns_exact_authenticated_identity(
    display_name: str | None,
) -> None:
    """Return the dependency-provided identity through the public HTTP contract."""

    user_account_uuid = uuid.UUID("018f5f45-9f18-7b65-b9d8-8d9acbc4ed43")
    application = FastAPI()
    application.include_router(router)

    def current_user_override() -> CurrentUser:
        """Provide one deterministic authenticated principal for this app."""

        return CurrentUser(
            user_account_uuid=user_account_uuid,
            subject="test_subject",
            display_name=display_name,
        )

    application.dependency_overrides[get_current_user] = current_user_override

    with TestClient(application) as client:
        response = client.get("/api/me")

    assert response.status_code == 200
    assert response.json() == {
        "user_account_uuid": str(user_account_uuid),
        "subject": "test_subject",
        "display_name": display_name,
    }
