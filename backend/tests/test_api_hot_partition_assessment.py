"""Tests for the ``/api/snapshots/{uuid}/hot-partition-assessment`` endpoint."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.api.snapshots import hot_partition_assessment
from app.auth import CurrentUser


def _user() -> CurrentUser:
    """Return a throwaway authenticated user."""

    return CurrentUser(
        user_account_uuid=uuid.uuid4(), subject="test", display_name="Test"
    )


_SNAPSHOT_JSON = {
    "relations": [
        {"relation_oid": 1, "schema_name": "public", "relation_name": "audit_event", "relation_kind": "r", "partition_key": None, "is_partition": False}
    ],
    "columns": [
        {"relation_oid": 1, "column_position": 1, "column_name": "audit_event_id", "data_type": "bigint", "is_not_null": True, "has_default": True, "default_expr": "nextval('s'::regclass)"},
        {"relation_oid": 1, "column_position": 2, "column_name": "occurred_at", "data_type": "timestamp with time zone", "is_not_null": True, "has_default": True, "default_expr": "now()"},
    ],
    "pk_columns": [{"relation_oid": 1, "column_name": "audit_event_id"}],
}


@pytest.mark.asyncio
async def test_returns_not_found_without_reading_data_when_unauthorized() -> None:
    session = AsyncMock()
    with patch(
        "app.api.snapshots._get_authorized_snapshot",
        new=AsyncMock(return_value=None),
    ):
        out = await hot_partition_assessment(
            schema_snapshot_uuid=uuid.uuid4(), user=_user(), session=session
        )
    assert out.status == "not_found"
    assert out.report is None
    session.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_returns_versioned_report_for_an_authorized_snapshot() -> None:
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(snapshot_json=_SNAPSHOT_JSON)
    snapshot_uuid = uuid.uuid4()
    with patch(
        "app.api.snapshots._get_authorized_snapshot",
        new=AsyncMock(return_value=SimpleNamespace(schema_snapshot_uuid=snapshot_uuid)),
    ):
        out = await hot_partition_assessment(
            schema_snapshot_uuid=snapshot_uuid, user=_user(), session=session
        )
    assert out.status == "ok"
    assert out.report is not None
    assert out.report["report_version"] == "1"
    kinds = {f["kind"] for f in out.report["findings"]}
    assert "append_heavy_table" in kinds
    assert "monotonic_key_hot_page" in kinds
    assert out.report["summary"]["relations_at_risk"] == 1


@pytest.mark.asyncio
async def test_missing_snapshot_data_row_is_handled_as_empty() -> None:
    session = AsyncMock()
    session.get.return_value = None
    snapshot_uuid = uuid.uuid4()
    with patch(
        "app.api.snapshots._get_authorized_snapshot",
        new=AsyncMock(return_value=SimpleNamespace(schema_snapshot_uuid=snapshot_uuid)),
    ):
        out = await hot_partition_assessment(
            schema_snapshot_uuid=snapshot_uuid, user=_user(), session=session
        )
    assert out.status == "ok"
    assert out.report is not None
    assert out.report["findings"] == []
