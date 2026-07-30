from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.share import (
    export_shared_snapshot_reversing_spec,
    get_shared_snapshot,
)

_SECRET_RELATION_COMMENT = "SECRET_RELATION_COMMENT internal only"
_SECRET_COLUMN_COMMENT = "SECRET_COLUMN_COMMENT contains PII notes"
_SECRET_EXAMPLE_VALUE = "secret-example-value@internal.example"


def _sensitive_snapshot() -> dict:
    """Build a snapshot whose comments/example values must never be shared."""

    return {
        "source_dialect": "postgresql",
        "server_version": "16.4",
        "captured_at": "2026-06-20T00:00:00+00:00",
        "relations": [
            {
                "schema_name": "public",
                "relation_name": "users",
                "relation_oid": 1,
                "relation_kind": "r",
                "relation_comment": _SECRET_RELATION_COMMENT,
            },
        ],
        "columns": [
            {
                "relation_oid": 1,
                "column_position": 1,
                "column_name": "email",
                "data_type": "text",
                "is_not_null": True,
                "example_value": _SECRET_EXAMPLE_VALUE,
                "column_comment": _SECRET_COLUMN_COMMENT,
            },
        ],
        "constraints": [],
        "indexes": [],
        "pk_columns": [],
        "fk_edges": [],
    }


def _share_session(snapshot_json: dict) -> AsyncMock:
    """Return a mocked session serving a valid link, snapshot, and data."""

    project_space_uuid = uuid.uuid4()
    schema_snapshot_uuid = uuid.uuid4()
    link = SimpleNamespace(
        expires_at=None,
        project_space_uuid=project_space_uuid,
    )
    snap = SimpleNamespace(
        schema_snapshot_uuid=schema_snapshot_uuid,
        project_space_uuid=project_space_uuid,
        status="ready",
        schema_filter="public",
        error_message=None,
    )
    data = SimpleNamespace(snapshot_json=snapshot_json)
    session = AsyncMock()
    session.get.side_effect = [link, snap, data]
    session._ids = (uuid.uuid4(), schema_snapshot_uuid)
    return session


@pytest.mark.asyncio
async def test_shared_snapshot_json_redacts_sensitive_fields() -> None:
    """The public JSON share route already redacts comments/example values."""

    session = _share_session(_sensitive_snapshot())
    share_uuid, snapshot_uuid = session._ids
    out = await get_shared_snapshot(
        share_link_uuid=share_uuid,
        schema_snapshot_uuid=snapshot_uuid,
        session=session,
    )
    payload = repr(out)
    assert _SECRET_RELATION_COMMENT not in payload
    assert _SECRET_COLUMN_COMMENT not in payload
    assert _SECRET_EXAMPLE_VALUE not in payload


@pytest.mark.asyncio
async def test_shared_reversing_spec_markdown_redacts_sensitive_fields() -> None:
    """The public reversing-spec share export must not leak sensitive fields."""

    session = _share_session(_sensitive_snapshot())
    share_uuid, snapshot_uuid = session._ids
    markdown = await export_shared_snapshot_reversing_spec(
        share_link_uuid=share_uuid,
        schema_snapshot_uuid=snapshot_uuid,
        mode="markdown",
        session=session,
    )
    assert _SECRET_RELATION_COMMENT not in markdown
    assert _SECRET_COLUMN_COMMENT not in markdown
    assert _SECRET_EXAMPLE_VALUE not in markdown
    # Non-sensitive structure is still present.
    assert "users" in markdown
    assert "email" in markdown


@pytest.mark.asyncio
async def test_shared_reversing_spec_llm_prompt_redacts_sensitive_fields() -> None:
    """The public reversing-spec LLM prompt must not leak sensitive fields."""

    session = _share_session(_sensitive_snapshot())
    share_uuid, snapshot_uuid = session._ids
    prompt = await export_shared_snapshot_reversing_spec(
        share_link_uuid=share_uuid,
        schema_snapshot_uuid=snapshot_uuid,
        mode="llm-prompt",
        session=session,
    )
    assert _SECRET_RELATION_COMMENT not in prompt
    assert _SECRET_COLUMN_COMMENT not in prompt
    assert _SECRET_EXAMPLE_VALUE not in prompt
