import datetime as dt
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

from app.api.diagram_views import (
    MAX_LAYOUT_BYTES,
    _bound_layout_size,
    _get_authorized_view,
    create_view,
    delete_view,
    get_view,
    list_views,
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


def _layout_with_non_ascii_serialized_size(serialized_bytes: int) -> dict[str, str]:
    """Build compact UTF-8 JSON at an exact size with a non-ASCII value."""

    fixed_bytes = len('{"blob":"한"}'.encode())
    if serialized_bytes < fixed_bytes:
        raise ValueError("serialized size is too small for the fixture")
    return {"blob": "한" + "a" * (serialized_bytes - fixed_bytes)}


def test_layout_limit_preserves_non_ascii_utf8_at_exact_boundary() -> None:
    """Measure stored Unicode as compact UTF-8 rather than ASCII escapes."""

    exact_layout = _layout_with_non_ascii_serialized_size(MAX_LAYOUT_BYTES)
    _bound_layout_size(exact_layout)

    with pytest.raises(HTTPException) as exc:
        _bound_layout_size(
            _layout_with_non_ascii_serialized_size(MAX_LAYOUT_BYTES + 1)
        )

    assert exc.value.status_code == 413


def test_layout_limit_preserves_well_formed_json_surrogate_escape() -> None:
    """Match JSON.stringify for a lone surrogate instead of failing to encode."""

    _bound_layout_size({"blob": "\ud800"})


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
async def test_create_view_persists_authorized_layout() -> None:
    """Persist and return a bounded layout after editor authorization."""

    session = AsyncMock()
    session.add = Mock()
    project_id = uuid.uuid4()
    user = _user()
    body = DiagramViewCreateIn(
        name="Architecture review",
        layout_json={"positions": {"public.member": {"x": 10, "y": 20}}},
    )

    with patch(
        "app.api.diagram_views.require_project_member", new_callable=AsyncMock
    ) as membership:
        out = await create_view(
            project_space_uuid=project_id,
            body=body,
            user=user,
            session=session,
        )

    membership.assert_awaited_once_with(
        session, project_id, user.user_account_uuid, minimum_role="editor"
    )
    session.add.assert_called_once()
    saved_view = session.add.call_args.args[0]
    assert saved_view.project_space_uuid == project_id
    assert saved_view.created_by == user.user_account_uuid
    assert saved_view.name == body.name
    assert saved_view.layout_json == body.layout_json
    assert out.diagram_view_uuid == saved_view.diagram_view_uuid
    assert out.created_at == saved_view.created_at
    assert out.updated_at == saved_view.updated_at
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_authorized_view_hides_missing_identity_before_membership_check() -> None:
    """Avoid authorization work when no saved-view identity exists."""

    session = AsyncMock()
    session.scalar.return_value = None
    user = _user()

    with patch(
        "app.api.diagram_views.require_project_member", new_callable=AsyncMock
    ) as membership:
        result = await _get_authorized_view(session, uuid.uuid4(), user)

    assert result is None
    membership.assert_not_awaited()
    session.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_authorized_view_returns_resource_after_membership_check() -> None:
    """Fetch the saved view only after the requested role is authorized."""

    session = AsyncMock()
    project_id = uuid.uuid4()
    view_id = uuid.uuid4()
    user = _user()
    persisted_view = SimpleNamespace(diagram_view_uuid=view_id)
    session.scalar.return_value = project_id
    session.get.return_value = persisted_view

    with patch(
        "app.api.diagram_views.require_project_member", new_callable=AsyncMock
    ) as membership:
        result = await _get_authorized_view(
            session, view_id, user, minimum_role="editor"
        )

    assert result is persisted_view
    membership.assert_awaited_once_with(
        session, project_id, user.user_account_uuid, minimum_role="editor"
    )
    session.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_authorized_view_hides_forbidden_membership() -> None:
    """Map forbidden membership to the same absence result as a missing view."""

    session = AsyncMock()
    session.scalar.return_value = uuid.uuid4()
    denied = HTTPException(status_code=403, detail="Forbidden")

    with patch(
        "app.api.diagram_views.require_project_member",
        new=AsyncMock(side_effect=denied),
    ):
        result = await _get_authorized_view(session, uuid.uuid4(), _user())

    assert result is None
    session.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_authorized_view_propagates_non_membership_http_errors() -> None:
    """Preserve unexpected authorization failures instead of masking them."""

    session = AsyncMock()
    session.scalar.return_value = uuid.uuid4()
    unavailable = HTTPException(status_code=503, detail="authorization unavailable")

    with patch(
        "app.api.diagram_views.require_project_member",
        new=AsyncMock(side_effect=unavailable),
    ):
        with pytest.raises(HTTPException) as exc:
            await _get_authorized_view(session, uuid.uuid4(), _user())

    assert exc.value is unavailable
    session.get.assert_not_awaited()


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


@pytest.mark.asyncio
async def test_delete_view_deletes_when_authorized() -> None:
    """Delete and commit exactly the authorized saved-view resource."""

    session = AsyncMock()
    view = SimpleNamespace(diagram_view_uuid=uuid.uuid4())
    with patch(
        "app.api.diagram_views._get_authorized_view",
        new_callable=AsyncMock,
        return_value=view,
    ):
        result = await delete_view(
            diagram_view_uuid=view.diagram_view_uuid, user=_user(), session=session
        )

    assert result == {"ok": True}
    session.delete.assert_called_once_with(view)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_views_returns_authorized_project_views() -> None:
    """Return the exact authorized project's persisted view summaries."""

    session = AsyncMock()
    project_id = uuid.uuid4()
    now = dt.datetime.now(dt.timezone.utc)
    views = [
        SimpleNamespace(
            diagram_view_uuid=uuid.uuid4(), name=name, created_at=now, updated_at=now
        )
        for name in ("view 1", "view 2")
    ]
    rows = Mock()
    rows.scalars.return_value.all.return_value = views
    session.execute.return_value = rows

    with patch(
        "app.api.diagram_views.require_project_member", new_callable=AsyncMock
    ) as membership:
        out = await list_views(
            project_space_uuid=project_id, user=_user(), session=session
        )

    assert [item.name for item in out] == ["view 1", "view 2"]
    membership.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_views_propagates_authorization_failure_before_query() -> None:
    """Fail authorization before querying project-scoped view identities."""

    session = AsyncMock()
    denied = HTTPException(status_code=403, detail="Forbidden")
    with patch(
        "app.api.diagram_views.require_project_member",
        new=AsyncMock(side_effect=denied),
    ):
        with pytest.raises(HTTPException) as exc:
            await list_views(
                project_space_uuid=uuid.uuid4(), user=_user(), session=session
            )

    assert exc.value.status_code == 403
    session.execute.assert_not_awaited()
