import datetime as dt
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

from app.api.annotations import (
    delete_annotation,
    list_annotations,
    upsert_annotation,
)
from app.auth import CurrentUser
from app.schemas import TableAnnotationUpsertIn


def _user():
    return CurrentUser(
        user_account_uuid=uuid.uuid4(), subject="test", display_name="Test"
    )


@pytest.mark.asyncio
async def test_delete_annotation_returns_404_when_missing_or_unauthorized():
    # Uniform 404 for both missing and unauthorized (no enumeration / IDOR).
    session = AsyncMock()
    with patch(
        "app.api.annotations._get_authorized_annotation",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with pytest.raises(HTTPException) as exc:
            await delete_annotation(
                table_annotation_uuid=uuid.uuid4(), user=_user(), session=session
            )
    assert exc.value.status_code == 404
    session.delete.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_creates_new_annotation_when_absent():
    session = AsyncMock()
    session.add = Mock()
    session.scalar = AsyncMock(return_value=None)  # no existing row
    body = TableAnnotationUpsertIn(
        schema_name="public", relation_name="orders", body="핵심 주문 테이블"
    )
    with patch(
        "app.api.annotations.require_project_member", new_callable=AsyncMock
    ):
        out = await upsert_annotation(
            project_space_uuid=uuid.uuid4(),
            body=body,
            user=_user(),
            session=session,
        )
    assert out.schema_name == "public"
    assert out.relation_name == "orders"
    assert out.body == "핵심 주문 테이블"
    session.add.assert_called_once()
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_upsert_updates_existing_annotation_without_insert():
    session = AsyncMock()
    session.add = Mock()
    now = dt.datetime.now(dt.timezone.utc)
    existing = SimpleNamespace(
        table_annotation_uuid=uuid.uuid4(),
        schema_name="public",
        relation_name="orders",
        body="old",
        created_at=now,
        updated_at=now,
    )
    session.scalar = AsyncMock(return_value=existing)
    body = TableAnnotationUpsertIn(
        schema_name="public", relation_name="orders", body="new note"
    )
    with patch(
        "app.api.annotations.require_project_member", new_callable=AsyncMock
    ):
        out = await upsert_annotation(
            project_space_uuid=uuid.uuid4(),
            body=body,
            user=_user(),
            session=session,
        )
    assert out.body == "new note"
    assert existing.body == "new note"  # updated in place, not re-inserted
    session.add.assert_not_called()
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_list_annotations_returns_project_notes():
    session = AsyncMock()
    now = dt.datetime.now(dt.timezone.utc)
    ann = SimpleNamespace(
        table_annotation_uuid=uuid.uuid4(),
        schema_name="public",
        relation_name="member",
        body="회원 마스터",
        created_at=now,
        updated_at=now,
    )
    result = SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=lambda: [ann])
    )
    session.execute = AsyncMock(return_value=result)
    with patch(
        "app.api.annotations.require_project_member", new_callable=AsyncMock
    ):
        out = await list_annotations(
            project_space_uuid=uuid.uuid4(), user=_user(), session=session
        )
    assert len(out) == 1
    assert out[0].relation_name == "member"
    assert out[0].body == "회원 마스터"
