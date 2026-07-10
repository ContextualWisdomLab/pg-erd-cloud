import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.api.snapshots import diff_snapshot
from app.auth import CurrentUser


def _user():
    return CurrentUser(
        user_account_uuid=uuid.uuid4(), subject="test", display_name="Test"
    )


@pytest.mark.asyncio
async def test_diff_returns_not_found_when_a_snapshot_is_unauthorized():
    # If either snapshot is missing/unauthorized, respond uniformly (no
    # existence enumeration) — mirrors get_snapshot's not_found contract.
    session = AsyncMock()
    target = uuid.uuid4()
    base = uuid.uuid4()

    with patch(
        "app.api.snapshots._get_authorized_snapshot",
        new_callable=AsyncMock,
        return_value=None,
    ):
        out = await diff_snapshot(
            schema_snapshot_uuid=target, against=base, user=_user(), session=session
        )

    assert out.status == "not_found"
    assert out.diff is None
    assert out.base_snapshot_uuid == base
    assert out.target_snapshot_uuid == target
    # Must not read snapshot data for an unauthorized request.
    session.get.assert_not_called()


@pytest.mark.asyncio
async def test_diff_computes_changes_when_both_authorized():
    session = AsyncMock()
    target = uuid.uuid4()
    base = uuid.uuid4()

    base_json = {
        "relations": [
            {"relation_oid": 1, "schema_name": "public", "relation_name": "member"}
        ],
        "columns": [
            {
                "relation_oid": 1,
                "column_name": "email",
                "data_type": "varchar(100)",
                "is_not_null": False,
            }
        ],
        "pk_columns": [],
        "fk_edges": [],
    }
    # Same table (different oid), email widened + NOT NULL, new table added.
    target_json = {
        "relations": [
            {"relation_oid": 50, "schema_name": "public", "relation_name": "member"},
            {"relation_oid": 51, "schema_name": "public", "relation_name": "orders"},
        ],
        "columns": [
            {
                "relation_oid": 50,
                "column_name": "email",
                "data_type": "varchar(255)",
                "is_not_null": True,
            },
            {
                "relation_oid": 51,
                "column_name": "order_id",
                "data_type": "bigint",
                "is_not_null": True,
            },
        ],
        "pk_columns": [],
        "fk_edges": [],
    }

    # Both snapshots authorized.
    authorized = AsyncMock(return_value=SimpleNamespace(schema_snapshot_uuid=target))
    # session.get(SchemaSnapshotData, against) then (…, target).
    session.get.side_effect = [
        SimpleNamespace(snapshot_json=base_json),
        SimpleNamespace(snapshot_json=target_json),
    ]

    with patch("app.api.snapshots._get_authorized_snapshot", authorized):
        out = await diff_snapshot(
            schema_snapshot_uuid=target, against=base, user=_user(), session=session
        )

    assert out.status == "ok"
    assert out.diff is not None
    assert out.diff["tables"]["added"] == ["public.orders"]
    assert out.diff["summary"]["columns_changed"] == 1
    assert out.diff["summary"]["has_changes"] is True
