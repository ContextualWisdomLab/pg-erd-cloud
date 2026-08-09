from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import Request

from app.api.auth_routes import logout


@pytest.mark.asyncio
async def test_logout_revokes_token_and_returns_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_revoke = AsyncMock()
    monkeypatch.setattr("app.api.auth_routes.revoke_current_request_token", mock_revoke)

    mock_request = Request(scope={"type": "http"})

    response = await logout(mock_request)

    mock_revoke.assert_awaited_once_with(mock_request)
    assert response == {"ok": True}
