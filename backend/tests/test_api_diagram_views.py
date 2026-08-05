import datetime as dt
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.api.diagram_views import (
    MAX_LAYOUT_BYTES,
    create_view,
    delete_view,
    get_view,
    update_view,
)
from app.auth import CurrentUser
from app.schemas import DiagramViewCreateIn


def _user() -> CurrentUser:
    """Build an authenticated test user with an opaque account identifier."""

    return CurrentUser(
        user_account_uuid=uuid.uuid4(), subject="test", display_name="Test"
    )


def _layout_with_serialized_size(serialized_bytes: int) -> dict[str, str]:
    """Build a compact JSON object whose UTF-8 encoding has the requested size."""

    fixed_bytes = len(b'{"blob":""}')
    if serialized_bytes < fixed_bytes:
        raise ValueError("serialized size is too small for the fixture")
    return {"blob": "a" * (serialized_bytes - fixed_bytes)}


@pytest.mark.asyncio
async def test_get_view_returns_404_when_missing_or_unauthorized() -> None:
    """Hide whether a requested view is missing or merely unauthorized."""

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
async def test_get_view_returns_detail_when_authorized() -> None:
    """Return the full saved layout to an authorized project member."""

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
async def test_create_view_rejects_oversized_layout() -> None:
    """Reject unbounded saved-layout payloads before persistence."""

    session = AsyncMock()
    body = DiagramViewCreateIn(
        name="big",
        layout_json=_layout_with_serialized_size(MAX_LAYOUT_BYTES + 1),
    )
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
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_view_replaces_name_and_layout_for_editor() -> None:
    """Replace a saved view in place without changing its stable identifier."""

    session = AsyncMock()
    user = _user()
    view_id = uuid.uuid4()
    created_at = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    previous_updated_at = dt.datetime(2026, 2, 1, tzinfo=dt.timezone.utc)
    view = SimpleNamespace(
        diagram_view_uuid=view_id,
        name="Original layout",
        layout_json={"positions": {"1": {"x": 0, "y": 0}}},
        created_at=created_at,
        updated_at=previous_updated_at,
    )
    body = DiagramViewCreateIn(
        name="Architecture review",
        layout_json={
            "positions": {
                "1": {"x": 120, "y": 48},
                "2": {"x": 560, "y": 48},
            },
            "viewport": {"x": 10, "y": 20, "zoom": 0.85},
        },
    )

    with patch(
        "app.api.diagram_views._get_authorized_view",
        new_callable=AsyncMock,
        return_value=view,
    ) as authorized_view:
        out = await update_view(
            diagram_view_uuid=view_id,
            body=body,
            user=user,
            session=session,
        )

    authorized_view.assert_awaited_once_with(
        session, view_id, user, minimum_role="editor"
    )
    assert view.diagram_view_uuid == view_id
    assert view.created_at == created_at
    assert view.name == "Architecture review"
    assert view.layout_json == body.layout_json
    assert view.updated_at > previous_updated_at
    assert out.diagram_view_uuid == view_id
    assert out.name == "Architecture review"
    assert out.created_at == created_at
    assert out.updated_at == view.updated_at
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_view_accepts_layout_at_exact_serialized_limit() -> None:
    """Accept a replacement whose compact JSON encoding is exactly 512 KiB."""

    session = AsyncMock()
    view_id = uuid.uuid4()
    created_at = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    view = SimpleNamespace(
        diagram_view_uuid=view_id,
        name="Original",
        layout_json={},
        created_at=created_at,
        updated_at=created_at,
    )
    exact_layout = _layout_with_serialized_size(MAX_LAYOUT_BYTES)

    with patch(
        "app.api.diagram_views._get_authorized_view",
        new_callable=AsyncMock,
        return_value=view,
    ):
        out = await update_view(
            diagram_view_uuid=view_id,
            body=DiagramViewCreateIn(name="At limit", layout_json=exact_layout),
            user=_user(),
            session=session,
        )

    assert view.layout_json == exact_layout
    assert out.name == "At limit"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_view_returns_404_without_editor_access() -> None:
    """Avoid revealing saved-view existence to unauthorized users."""

    session = AsyncMock()
    with patch(
        "app.api.diagram_views._get_authorized_view",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with pytest.raises(HTTPException) as exc:
            await update_view(
                diagram_view_uuid=uuid.uuid4(),
                body=DiagramViewCreateIn(name="Updated", layout_json={}),
                user=_user(),
                session=session,
            )

    assert exc.value.status_code == 404
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_view_rejects_one_byte_over_limit_before_mutation() -> None:
    """Keep the prior view unchanged when serialized layout is one byte too large."""

    session = AsyncMock()
    view_id = uuid.uuid4()
    original_layout = {"positions": {"1": {"x": 0, "y": 0}}}
    original_updated_at = dt.datetime(2026, 2, 1, tzinfo=dt.timezone.utc)
    view = SimpleNamespace(
        diagram_view_uuid=view_id,
        name="Original",
        layout_json=original_layout,
        created_at=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
        updated_at=original_updated_at,
    )
    body = DiagramViewCreateIn(
        name="Oversized",
        layout_json=_layout_with_serialized_size(MAX_LAYOUT_BYTES + 1),
    )

    with patch(
        "app.api.diagram_views._get_authorized_view",
        new_callable=AsyncMock,
        return_value=view,
    ):
        with pytest.raises(HTTPException) as exc:
            await update_view(
                diagram_view_uuid=view_id,
                body=body,
                user=_user(),
                session=session,
            )

    assert exc.value.status_code == 413
    assert view.name == "Original"
    assert view.layout_json == original_layout
    assert view.updated_at == original_updated_at
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_view_returns_404_when_unauthorized() -> None:
    """Return a uniform not-found response for unauthorized deletion."""

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
