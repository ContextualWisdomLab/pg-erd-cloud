from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
import uuid

@pytest.mark.asyncio
async def test_create_view_returns_422_when_name_has_control_characters():
    from app.auth import get_current_user, CurrentUser
    def mock_get_current_user():
        return CurrentUser(user_account_uuid=uuid.uuid4(), subject="test", display_name="Test")
    app.dependency_overrides[get_current_user] = mock_get_current_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        csrf_res = await ac.get("/api/csrf-token")
        token = csrf_res.json()["csrf_token"]

        response = await ac.post(
            f"/api/diagram-views/by-project/{uuid.uuid4()}",
            json={"name": "invalid\nname", "layout_json": {}},
            headers={
                "X-CSRF-Token": token,
                "Origin": "http://test",
                "Referer": "http://test/"
            }
        )
    assert response.status_code == 422
    assert "string_pattern_mismatch" in response.text

@pytest.mark.asyncio
async def test_create_api_key_returns_422_when_key_name_has_control_characters():
    from app.auth import get_current_user, CurrentUser
    def mock_get_current_user():
        return CurrentUser(user_account_uuid=uuid.uuid4(), subject="test", display_name="Test")
    app.dependency_overrides[get_current_user] = mock_get_current_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        csrf_res = await ac.get("/api/csrf-token")
        token = csrf_res.json()["csrf_token"]

        response = await ac.post(
            "/api/api-keys",
            json={"key_name": "invalid\nkey"},
            headers={
                "X-CSRF-Token": token,
                "Origin": "http://test",
                "Referer": "http://test/"
            }
        )
    assert response.status_code == 422
    assert "string_pattern_mismatch" in response.text
