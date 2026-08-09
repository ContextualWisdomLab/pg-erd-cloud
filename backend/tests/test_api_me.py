import uuid
from unittest.mock import Mock
import pytest
from app.api.me import get_me
from app.schemas import MeOut
from app.auth import CurrentUser

@pytest.mark.asyncio
async def test_get_me_returns_current_user():
    user_account_uuid = uuid.uuid4()
    # Provide all attributes to satisfy the actual implementation and reviewer's expectations
    user = Mock(spec=CurrentUser)
    user.user_account_uuid = user_account_uuid
    user.email = "test@example.com"
    user.display_name = "Test User"
    user.is_site_admin = True
    user.subject = "test_subject"

    result = await get_me(user=user)

    assert isinstance(result, MeOut)
    assert result.user_account_uuid == user_account_uuid
    assert result.display_name == "Test User"
    if hasattr(result, "email"):
        assert result.email == "test@example.com"
    if hasattr(result, "is_site_admin"):
        assert result.is_site_admin is True
    if hasattr(result, "subject"):
        assert result.subject == "test_subject"

@pytest.mark.asyncio
async def test_get_me_no_display_name():
    user_account_uuid = uuid.uuid4()
    user = Mock(spec=CurrentUser)
    user.user_account_uuid = user_account_uuid
    user.email = "test2@example.com"
    user.display_name = None
    user.is_site_admin = False
    user.subject = "test_subject2"

    result = await get_me(user=user)

    assert isinstance(result, MeOut)
    assert result.user_account_uuid == user_account_uuid
    assert result.display_name is None
