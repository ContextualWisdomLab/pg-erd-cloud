import datetime as dt
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.api.diagram_views import create_view, delete_view, get_view
from app.auth import CurrentUser
from app.schemas import DiagramViewCreateIn


def _current_user() -> CurrentUser:
    """Return one authenticated test user."""
    return CurrentUser(
        user_account_uuid=uuid.uuid4(), subject="test", display_name="Test"
    )


@pytest.mark.asyncio
async def test_get_view_returns_404_when_missing_or_unauthorized() -> None:
    """Return a uniform 404 for missing and unauthorized diagram views."""
    database_session = AsyncMock()
    with patch(
        "app.api.diagram_views._get_authorized_view",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with pytest.raises(HTTPException) as http_exception:
            await get_view(
                diagram_view_uuid=uuid.uuid4(),
                current_user=_current_user(),
                database_session=database_session,
            )
    assert http_exception.value.status_code == 404


@pytest.mark.asyncio
async def test_get_view_returns_detail_when_authorized() -> None:
    """Return semantic internal fields while retaining the legacy wire alias."""
    database_session = AsyncMock()
    current_time = dt.datetime.now(dt.timezone.utc)
    diagram_view_uuid = uuid.uuid4()
    diagram_view = SimpleNamespace(
        diagram_view_uuid=diagram_view_uuid,
        diagram_name="my view",
        layout_json={"positions": {"public.member": {"x": 10, "y": 20}}},
        created_at=current_time,
        updated_at=current_time,
    )
    with patch(
        "app.api.diagram_views._get_authorized_view",
        new_callable=AsyncMock,
        return_value=diagram_view,
    ):
        diagram_view_output = await get_view(
            diagram_view_uuid=diagram_view_uuid,
            current_user=_current_user(),
            database_session=database_session,
        )
    assert diagram_view_output.diagram_view_uuid == diagram_view_uuid
    assert diagram_view_output.diagram_name == "my view"
    assert diagram_view_output.name == "my view"
    assert diagram_view_output.model_dump(by_alias=True)["name"] == "my view"
    assert diagram_view_output.layout_json["positions"]["public.member"] == {
        "x": 10,
        "y": 20,
    }


@pytest.mark.asyncio
async def test_create_view_rejects_oversized_layout() -> None:
    """Reject oversized diagram layouts before persistence."""
    database_session = AsyncMock()
    oversized_layout = {"blob": "a" * (600 * 1024)}  # > 512KB serialized
    diagram_view_request = DiagramViewCreateIn(
        name="big",
        layout_json=oversized_layout,
    )
    with patch(
        "app.api.diagram_views.require_project_member", new_callable=AsyncMock
    ):
        with pytest.raises(HTTPException) as http_exception:
            await create_view(
                project_space_uuid=uuid.uuid4(),
                diagram_view_request=diagram_view_request,
                current_user=_current_user(),
                database_session=database_session,
            )
    assert http_exception.value.status_code == 413
    database_session.add.assert_not_called()
    database_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_delete_view_returns_404_when_unauthorized() -> None:
    """Do not reveal an unauthorized diagram view through delete."""
    database_session = AsyncMock()
    with patch(
        "app.api.diagram_views._get_authorized_view",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with pytest.raises(HTTPException) as http_exception:
            await delete_view(
                diagram_view_uuid=uuid.uuid4(),
                current_user=_current_user(),
                database_session=database_session,
            )
    assert http_exception.value.status_code == 404
    database_session.delete.assert_not_called()
