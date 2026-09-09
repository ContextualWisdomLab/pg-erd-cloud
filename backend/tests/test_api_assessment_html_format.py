"""``?format=html`` behaviour of the two assessment endpoints."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.responses import HTMLResponse

from app.api.snapshots import hot_partition_assessment, normalization_assessment
from app.auth import CurrentUser

_SNAPSHOT_JSON = {
    "relations": [
        {"relation_oid": 1, "schema_name": "public", "relation_name": "job_queue", "relation_kind": "r", "partition_key": None, "is_partition": False}
    ],
    "columns": [
        {"relation_oid": 1, "column_position": 1, "column_name": "job_id", "data_type": "bigint", "is_not_null": True, "has_default": True, "default_expr": "nextval('s'::regclass)"},
        {"relation_oid": 1, "column_position": 2, "column_name": "enqueued_at", "data_type": "timestamp with time zone", "is_not_null": True, "has_default": True, "default_expr": "now()"},
    ],
    "pk_columns": [{"relation_oid": 1, "column_name": "job_id"}],
}


def _user() -> CurrentUser:
    """Return a throwaway authenticated user."""

    return CurrentUser(
        user_account_uuid=uuid.uuid4(), subject="test", display_name="Test"
    )


def _authorized_session() -> AsyncMock:
    """An AsyncMock session that returns the fixture snapshot data row."""

    session = AsyncMock()
    session.get.return_value = SimpleNamespace(snapshot_json=_SNAPSHOT_JSON)
    return session


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "endpoint,title",
    [
        (normalization_assessment, "Normalization assessment"),
        (hot_partition_assessment, "Hot-partition assessment"),
    ],
)
async def test_format_html_returns_an_html_response(endpoint, title) -> None:
    snapshot_uuid = uuid.uuid4()
    with patch(
        "app.api.snapshots._get_authorized_snapshot",
        new=AsyncMock(return_value=SimpleNamespace(schema_snapshot_uuid=snapshot_uuid)),
    ):
        out = await endpoint(
            schema_snapshot_uuid=snapshot_uuid,
            format="html",
            user=_user(),
            session=_authorized_session(),
        )
    assert isinstance(out, HTMLResponse)
    body = out.body.decode()
    assert "cwl-assessment" in body
    assert f"<h1>{title}</h1>" in body


@pytest.mark.asyncio
async def test_format_json_is_the_default() -> None:
    snapshot_uuid = uuid.uuid4()
    with patch(
        "app.api.snapshots._get_authorized_snapshot",
        new=AsyncMock(return_value=SimpleNamespace(schema_snapshot_uuid=snapshot_uuid)),
    ):
        out = await normalization_assessment(
            schema_snapshot_uuid=snapshot_uuid,
            user=_user(),
            session=_authorized_session(),
        )
    assert not isinstance(out, HTMLResponse)
    assert out.status == "ok"
    assert out.report["report_version"] == "1"


@pytest.mark.asyncio
async def test_not_found_stays_uniform_json_even_with_format_html() -> None:
    session = AsyncMock()
    with patch(
        "app.api.snapshots._get_authorized_snapshot",
        new=AsyncMock(return_value=None),
    ):
        out = await hot_partition_assessment(
            schema_snapshot_uuid=uuid.uuid4(),
            format="html",
            user=_user(),
            session=session,
        )
    assert not isinstance(out, HTMLResponse)
    assert out.status == "not_found"
    assert out.report is None
    session.get.assert_not_awaited()
