"""Direct API contracts for the authenticated current-user endpoint."""

from __future__ import annotations

import uuid

import pytest

from app.api.me import get_me
from app.auth import CurrentUser
from app.schemas import MeOut


@pytest.mark.asyncio
async def test_get_me_returns_authenticated_current_user() -> None:
    """Map the authenticated principal to the public current-user response."""
    user_account_uuid = uuid.uuid4()
    user = CurrentUser(
        user_account_uuid=user_account_uuid,
        subject="oidc|buyer-user",
        display_name="Buyer User",
    )

    result = await get_me(user=user)

    assert isinstance(result, MeOut)
    assert result.user_account_uuid == user_account_uuid
    assert result.subject == "oidc|buyer-user"
    assert result.display_name == "Buyer User"
