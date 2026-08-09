import datetime as dt
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.api.diagram_views import create_view, delete_view, get_view, list_views
from app.auth import CurrentUser
from app.schemas import DiagramViewCreateIn


def _user():
    return CurrentUser(
        user_account_uuid=uuid.uuid4(), subject="test", display_name="Test"
    )


@pytest.mark.asyncio
async def test_get_view_returns_404_when_missing_or_unauthorized():
    # Uniform 404 for both missing and unauthorized (no enumeration).
    session = AsyncMock()
    with patch(
        "app.api.diagram_views._get_authorized_view",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with pytest.raises(HTTPException) as exc:
            await get_view(
                diagram_view_uuid=uuid.uuid4(), user=_user(), session=session
            )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_view_returns_detail_when_authorized():
    session = AsyncMock()
    now = dt.datetime.now(dt.timezone.utc)
    view_id = uuid.uuid4()
    view = SimpleNamespace(
        diagram_view_uuid=view_id,
        name="my view",
        layout_json={"positions": {"public.member": {"x": 10, "y": 20}}},
        created_at=now,
        updated_at=now,
    )
    with patch(
        "app.api.diagram_views._get_authorized_view",
        new_callable=AsyncMock,
        return_value=view,
    ):
        out = await get_view(
            diagram_view_uuid=view_id, user=_user(), session=session
        )
    assert out.diagram_view_uuid == view_id
    assert out.name == "my view"
    assert out.layout_json["positions"]["public.member"] == {"x": 10, "y": 20}


@pytest.mark.asyncio
async def test_create_view_rejects_oversized_layout():
    session = AsyncMock()
    huge = {"blob": "a" * (600 * 1024)}  # > 512KB serialized
    body = DiagramViewCreateIn(name="big", layout_json=huge)
    with patch(
        "app.api.diagram_views.require_project_member", new_callable=AsyncMock
    ):
        with pytest.raises(HTTPException) as exc:
            await create_view(
                project_space_uuid=uuid.uuid4(),
                body=body,
                user=_user(),
                session=session,
            )
    assert exc.value.status_code == 413
    # Nothing should have been persisted.
    session.add.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_delete_view_returns_404_when_unauthorized():
    session = AsyncMock()
    with patch(
        "app.api.diagram_views._get_authorized_view",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with pytest.raises(HTTPException) as exc:
            await delete_view(
                diagram_view_uuid=uuid.uuid4(), user=_user(), session=session
            )
    assert exc.value.status_code == 404
    session.delete.assert_not_called()


@pytest.mark.asyncio
async def test_list_views_returns_list_when_authorized():
    session = AsyncMock()
    project_id = uuid.uuid4()
    view_id1 = uuid.uuid4()
    view_id2 = uuid.uuid4()
    now = dt.datetime.now(dt.timezone.utc)

    view1 = SimpleNamespace(
        diagram_view_uuid=view_id1,
        name="view 1",
        created_at=now,
        updated_at=now,
    )
    view2 = SimpleNamespace(
        diagram_view_uuid=view_id2,
        name="view 2",
        created_at=now,
        updated_at=now,
    )

    from unittest.mock import Mock
    rows_mock = Mock()
    rows_mock.scalars.return_value.all.return_value = [view1, view2]
    session.execute.return_value = rows_mock

    with patch(
        "app.api.diagram_views.require_project_member", new_callable=AsyncMock
    ) as mock_require:
        out = await list_views(
            project_space_uuid=project_id, user=_user(), session=session
        )

        mock_require.assert_called_once()
        assert len(out) == 2
        assert out[0].diagram_view_uuid == view_id1
        assert out[0].name == "view 1"
        assert out[1].diagram_view_uuid == view_id2
        assert out[1].name == "view 2"


@pytest.mark.asyncio
async def test_list_views_raises_when_unauthorized():
    session = AsyncMock()

    with patch(
        "app.api.diagram_views.require_project_member", new_callable=AsyncMock
    ) as mock_require:
        mock_require.side_effect = HTTPException(status_code=403, detail="Forbidden")

        with pytest.raises(HTTPException) as exc:
            await list_views(
                project_space_uuid=uuid.uuid4(), user=_user(), session=session
            )

        assert exc.value.status_code == 403
