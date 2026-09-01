"""Tests for the ``/api/snapshots/{uuid}/normalization-assessment`` endpoint."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.api.snapshots import normalization_assessment
from app.auth import CurrentUser


def _user() -> CurrentUser:
    """Return a throwaway authenticated user."""

    return CurrentUser(
        user_account_uuid=uuid.uuid4(), subject="test", display_name="Test"
    )


_SNAPSHOT_JSON = {
    "relations": [
        {"relation_oid": 1, "schema_name": "public", "relation_name": "order_line", "relation_kind": "r"}
    ],
    "columns": [
        {"relation_oid": 1, "column_position": 1, "column_name": "order_id", "data_type": "bigint", "is_not_null": True},
        {"relation_oid": 1, "column_position": 2, "column_name": "product_id", "data_type": "bigint", "is_not_null": True},
        {"relation_oid": 1, "column_position": 3, "column_name": "product_name", "data_type": "text", "is_not_null": True},
    ],
    "pk_columns": [
        {"relation_oid": 1, "column_name": "order_id"},
        {"relation_oid": 1, "column_name": "product_id"},
    ],
}


@pytest.mark.asyncio
async def test_returns_not_found_without_reading_data_when_unauthorized() -> None:
    session = AsyncMock()
    snapshot_uuid = uuid.uuid4()
    with patch(
        "app.api.snapshots._get_authorized_snapshot",
        new=AsyncMock(return_value=None),
    ):
        out = await normalization_assessment(
            schema_snapshot_uuid=snapshot_uuid, user=_user(), session=session
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
        out = await normalization_assessment(
            schema_snapshot_uuid=snapshot_uuid, user=_user(), session=session
        )
    assert out.status == "ok"
    assert out.report is not None
    assert out.report["report_version"] == "1"
    assert out.report["schema_fingerprint"].startswith("sha256:")
    # order_line has a composite-only key + a non-key column -> 2NF review.
    kinds = {f["kind"] for f in out.report["findings"]}
    assert "partial_dependency_precondition" in kinds
    assert out.report["summary"]["relations_needing_review"] == 1


@pytest.mark.asyncio
async def test_missing_snapshot_data_row_is_handled_as_empty() -> None:
    session = AsyncMock()
    session.get.return_value = None
    snapshot_uuid = uuid.uuid4()
    with patch(
        "app.api.snapshots._get_authorized_snapshot",
        new=AsyncMock(return_value=SimpleNamespace(schema_snapshot_uuid=snapshot_uuid)),
    ):
        out = await normalization_assessment(
            schema_snapshot_uuid=snapshot_uuid, user=_user(), session=session
        )
    assert out.status == "ok"
    assert out.report is not None
    assert out.report["findings"] == []
    assert out.report["summary"]["relations_assessed"] == 0
