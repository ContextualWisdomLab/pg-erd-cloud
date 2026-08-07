import uuid
import pytest
from app.api.me import get_me
from app.auth import CurrentUser
from app.schemas import MeOut

@pytest.mark.asyncio
async def test_get_me_returns_current_user_info():
    test_uuid = uuid.uuid4()
    user = CurrentUser(
        user_account_uuid=test_uuid,
        subject="test_subject",
        display_name="Test User"
    )

    result = await get_me(user=user)

    assert isinstance(result, MeOut)
    assert result.user_account_uuid == test_uuid
    assert result.subject == "test_subject"
    assert result.display_name == "Test User"
