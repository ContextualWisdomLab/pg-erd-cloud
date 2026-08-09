from __future__ import annotations

import datetime as dt
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from app.api.share import (
    _redact_sensitive_snapshot_fields,
    create_share_link,
    export_shared_snapshot_index_design,
    export_shared_snapshot_reversing_spec,
    export_shared_snapshot_sql,
    get_share_link_info,
    get_shared_snapshot,
    revoke_share_link,
    router,
)
from app.db import get_session

_SECRET_RELATION_COMMENT = "SECRET_RELATION_COMMENT internal only"
_SECRET_COLUMN_COMMENT = "SECRET_COLUMN_COMMENT contains PII notes"
_SECRET_EXAMPLE_VALUE = "secret-example-value@internal.example"
_SECRET_ERROR_MESSAGE = "host=db.internal user=admin TLS path=/secret"
_SECRET_WRONG_PATH = "secret-from-wrong-path"

_PUBLIC_SHARE_ENDPOINTS = [
    (get_share_link_info, {}),
    (get_shared_snapshot, {"schema_snapshot_uuid": uuid.uuid4()}),
    (
        export_shared_snapshot_sql,
        {"schema_snapshot_uuid": uuid.uuid4(), "dialect": "postgresql"},
    ),
    (
        export_shared_snapshot_reversing_spec,
        {"schema_snapshot_uuid": uuid.uuid4(), "mode": "markdown"},
    ),
    (
        export_shared_snapshot_index_design,
        {"schema_snapshot_uuid": uuid.uuid4(), "mode": "markdown"},
    ),
]


def _sensitive_snapshot() -> dict:
    """Build a snapshot whose comments/example values must never be shared."""

    return {
        "source_dialect": "postgresql",
        "database_name": "public-demo-database",
        "server_version": "16.4",
        "captured_at": "2026-06-20T00:00:00+00:00",
        "future_private_metadata": "must not cross the public schema boundary",
        "schemas": [
            {
                "schema_oid": 10,
                "schema_name": "public",
                "database_name": _SECRET_WRONG_PATH,
            },
            "legacy_schema",
        ],
        "relations": [
            {
                "schema_name": "public",
                "relation_name": "users",
                "relation_oid": 1,
                "relation_kind": "r",
                "relation_comment": _SECRET_RELATION_COMMENT,
                "future_owner_email": "owner@internal.example",
                "database_name": _SECRET_WRONG_PATH,
                "columns": [{"database_name": _SECRET_WRONG_PATH}],
            },
            _SECRET_WRONG_PATH,
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
        status="succeeded",
        schema_filter="public",
        error_message=_SECRET_ERROR_MESSAGE,
    )
    data = SimpleNamespace(snapshot_json=snapshot_json)
    session = AsyncMock()
    session.get.side_effect = [link, snap, data]
    session._ids = (uuid.uuid4(), schema_snapshot_uuid)
    return session


@pytest.mark.asyncio
async def test_create_share_link_requires_owner_role() -> None:
    """A non-owner must not be able to create a public bearer link."""

    row = MagicMock()
    row.scalar_one_or_none.return_value = "editor"
    session = SimpleNamespace(
        execute=AsyncMock(return_value=row),
        add=MagicMock(),
        commit=AsyncMock(),
    )
    user = SimpleNamespace(user_account_uuid=uuid.uuid4())

    with pytest.raises(HTTPException) as exc_info:
        await create_share_link(
            project_space_uuid=uuid.uuid4(),
            user=user,
            session=session,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "owner role required"
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_owner_can_create_share_link() -> None:
    """An owner receives a viewer link that is persisted for the project."""

    row = MagicMock()
    row.scalar_one_or_none.return_value = "owner"
    session = SimpleNamespace(
        execute=AsyncMock(return_value=row),
        add=MagicMock(),
        commit=AsyncMock(),
    )
    project_space_uuid = uuid.uuid4()
    user = SimpleNamespace(user_account_uuid=uuid.uuid4())

    out = await create_share_link(
        project_space_uuid=project_space_uuid,
        user=user,
        session=session,
    )

    added_link = session.add.call_args.args[0]
    assert added_link.project_space_uuid == project_space_uuid
    assert added_link.created_by_user_uuid == user.user_account_uuid
    assert added_link.expires_at is not None
    assert dt.timedelta(days=6, hours=23) < (
        added_link.expires_at - added_link.created_at
    ) <= dt.timedelta(days=7)
    assert out == {
        "share_link_uuid": str(added_link.share_link_uuid),
        "permission_kind": "viewer",
        "url_path": f"/api/share/{added_link.share_link_uuid}",
        "expires_at": added_link.expires_at.isoformat(),
    }
    session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_owner_can_revoke_share_link() -> None:
    """An owner can invalidate a bearer link before its expiry."""

    project_space_uuid = uuid.uuid4()
    share_link_uuid = uuid.uuid4()
    row = MagicMock()
    row.scalar_one_or_none.return_value = "owner"
    link = SimpleNamespace(
        share_link_uuid=share_link_uuid,
        project_space_uuid=project_space_uuid,
    )
    session = SimpleNamespace(
        execute=AsyncMock(return_value=row),
        get=AsyncMock(return_value=link),
        delete=AsyncMock(),
        commit=AsyncMock(),
    )
    user = SimpleNamespace(user_account_uuid=uuid.uuid4())

    response = await revoke_share_link(
        project_space_uuid=project_space_uuid,
        share_link_uuid=share_link_uuid,
        user=user,
        session=session,
    )

    assert response.status_code == 204
    session.delete.assert_awaited_once_with(link)
    session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_revoke_share_link_requires_owner_role() -> None:
    """An editor cannot revoke a project's bearer link."""

    row = MagicMock()
    row.scalar_one_or_none.return_value = "editor"
    session = SimpleNamespace(
        execute=AsyncMock(return_value=row),
        get=AsyncMock(),
        delete=AsyncMock(),
        commit=AsyncMock(),
    )

    with pytest.raises(HTTPException) as exc_info:
        await revoke_share_link(
            project_space_uuid=uuid.uuid4(),
            share_link_uuid=uuid.uuid4(),
            user=SimpleNamespace(user_account_uuid=uuid.uuid4()),
            session=session,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "owner role required"
    session.get.assert_not_awaited()
    session.delete.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_revoke_share_link_rejects_cross_project_link() -> None:
    """An owner cannot revoke a link belonging to a different project."""

    row = MagicMock()
    row.scalar_one_or_none.return_value = "owner"
    session = SimpleNamespace(
        execute=AsyncMock(return_value=row),
        get=AsyncMock(
            return_value=SimpleNamespace(project_space_uuid=uuid.uuid4())
        ),
        delete=AsyncMock(),
        commit=AsyncMock(),
    )

    with pytest.raises(HTTPException) as exc_info:
        await revoke_share_link(
            project_space_uuid=uuid.uuid4(),
            share_link_uuid=uuid.uuid4(),
            user=SimpleNamespace(user_account_uuid=uuid.uuid4()),
            session=session,
        )

    assert exc_info.value.status_code == 404
    session.delete.assert_not_awaited()
    session.commit.assert_not_awaited()


def test_public_share_routes_validate_links_on_the_primary_session() -> None:
    """Replica lag must not keep a revoked bearer link readable."""

    public_routes = [
        route
        for route in router.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/share/")
    ]

    assert public_routes
    for route in public_routes:
        session_dependencies = [
            dependency
            for dependency in route.dependant.dependencies
            if dependency.name == "session"
        ]
        assert len(session_dependencies) == 1
        assert session_dependencies[0].call is get_session


def test_public_snapshot_projection_is_path_and_type_scoped() -> None:
    """Allowed names at the wrong level or with object values fail closed."""

    projected = _redact_sensitive_snapshot_fields(
        {
            "source": {"database_name": _SECRET_WRONG_PATH},
            "constraints": [
                {
                    123: _SECRET_WRONG_PATH,
                    "constraint_oid": 1,
                    "constrained_attnums": [
                        1,
                        {"database_name": _SECRET_WRONG_PATH},
                    ],
                    "check_expr": {"relation_name": _SECRET_WRONG_PATH},
                }
            ],
        }
    )

    assert projected == {
        "constraints": [{"constraint_oid": 1, "constrained_attnums": [1]}]
    }
    assert _redact_sensitive_snapshot_fields([_SECRET_WRONG_PATH]) == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(("endpoint", "kwargs"), _PUBLIC_SHARE_ENDPOINTS)
async def test_public_share_endpoints_reject_unknown_links(endpoint, kwargs) -> None:
    """Every bearer-link endpoint must reject an unknown link before other reads."""

    session = AsyncMock()
    session.get.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await endpoint(share_link_uuid=uuid.uuid4(), session=session, **kwargs)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "share link not found"
    assert session.get.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(("endpoint", "kwargs"), _PUBLIC_SHARE_ENDPOINTS)
async def test_public_share_endpoints_reject_expired_links(endpoint, kwargs) -> None:
    """Every bearer-link endpoint must stop serving an expired link."""

    link = SimpleNamespace(
        expires_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1),
        project_space_uuid=uuid.uuid4(),
        permission_kind="viewer",
    )
    session = AsyncMock()
    session.get.return_value = link

    with pytest.raises(HTTPException) as exc_info:
        await endpoint(share_link_uuid=uuid.uuid4(), session=session, **kwargs)

    assert exc_info.value.status_code == 410
    assert exc_info.value.detail == "share link expired"
    assert session.get.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exporter", "kwargs", "expected"),
    [
        (
            export_shared_snapshot_sql,
            {"dialect": "postgresql"},
            "-- snapshot data not found\n",
        ),
        (
            export_shared_snapshot_reversing_spec,
            {"mode": "markdown"},
            "# DB Reversing Specification\n\nSnapshot data not found.\n",
        ),
        (
            export_shared_snapshot_index_design,
            {"mode": "markdown"},
            "# ERD Index Design\n\nSnapshot data not found.\n",
        ),
    ],
)
async def test_public_exports_handle_missing_snapshot_data(
    exporter, kwargs, expected
) -> None:
    """A succeeded snapshot without its data row returns a safe empty export."""

    project_space_uuid = uuid.uuid4()
    link = SimpleNamespace(expires_at=None, project_space_uuid=project_space_uuid)
    snapshot = SimpleNamespace(
        project_space_uuid=project_space_uuid,
        status="succeeded",
    )
    session = AsyncMock()
    session.get.side_effect = [link, snapshot, None]

    out = await exporter(
        share_link_uuid=uuid.uuid4(),
        schema_snapshot_uuid=uuid.uuid4(),
        session=session,
        **kwargs,
    )

    assert out == expected


@pytest.mark.asyncio
async def test_share_info_exposes_only_successful_snapshots() -> None:
    """Failed and in-progress snapshot metadata must not cross the public boundary."""

    project_space_uuid = uuid.uuid4()
    link = SimpleNamespace(
        expires_at=None,
        project_space_uuid=project_space_uuid,
        permission_kind="viewer",
    )
    failed = SimpleNamespace(
        schema_snapshot_uuid=uuid.uuid4(),
        project_space_uuid=project_space_uuid,
        status="failed",
        schema_filter="private",
        created_at=SimpleNamespace(isoformat=lambda: "2026-08-09T00:00:00+00:00"),
    )
    succeeded = SimpleNamespace(
        schema_snapshot_uuid=uuid.uuid4(),
        project_space_uuid=project_space_uuid,
        status="succeeded",
        schema_filter="public",
        created_at=SimpleNamespace(isoformat=lambda: "2026-08-09T01:00:00+00:00"),
    )
    rows = MagicMock()
    rows.scalars.return_value.all.return_value = [failed, succeeded]
    session = AsyncMock()
    session.get.return_value = link
    session.execute.return_value = rows

    out = await get_share_link_info(share_link_uuid=uuid.uuid4(), session=session)

    assert out["snapshots"] == [
        {
            "schema_snapshot_uuid": str(succeeded.schema_snapshot_uuid),
            "status": "succeeded",
            "schema_filter": "public",
            "created_at": "2026-08-09T01:00:00+00:00",
        }
    ]


@pytest.mark.asyncio
async def test_failed_snapshot_detail_is_not_public() -> None:
    """A public link must not reveal a failed snapshot or its diagnostic message."""

    project_space_uuid = uuid.uuid4()
    link = SimpleNamespace(expires_at=None, project_space_uuid=project_space_uuid)
    failed = SimpleNamespace(
        schema_snapshot_uuid=uuid.uuid4(),
        project_space_uuid=project_space_uuid,
        status="failed",
        schema_filter="private",
        error_message="host=db.internal user=admin TLS certificate path=/secret",
    )
    session = AsyncMock()
    session.get.side_effect = [link, failed]

    with pytest.raises(HTTPException) as exc_info:
        await get_shared_snapshot(
            share_link_uuid=uuid.uuid4(),
            schema_snapshot_uuid=failed.schema_snapshot_uuid,
            session=session,
        )

    assert exc_info.value.status_code == 404
    assert session.get.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exporter", "kwargs"),
    [
        (export_shared_snapshot_sql, {"dialect": "postgresql"}),
        (export_shared_snapshot_reversing_spec, {"mode": "markdown"}),
        (export_shared_snapshot_index_design, {"mode": "markdown"}),
    ],
)
async def test_failed_snapshot_exports_are_not_public(exporter, kwargs) -> None:
    """Every bearer-link export must enforce the successful-snapshot boundary."""

    project_space_uuid = uuid.uuid4()
    link = SimpleNamespace(expires_at=None, project_space_uuid=project_space_uuid)
    failed = SimpleNamespace(
        schema_snapshot_uuid=uuid.uuid4(),
        project_space_uuid=project_space_uuid,
        status="failed",
    )
    session = AsyncMock()
    session.get.side_effect = [link, failed]

    with pytest.raises(HTTPException) as exc_info:
        await exporter(
            share_link_uuid=uuid.uuid4(),
            schema_snapshot_uuid=failed.schema_snapshot_uuid,
            session=session,
            **kwargs,
        )

    assert exc_info.value.status_code == 404
    assert session.get.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exporter",
    [export_shared_snapshot_reversing_spec, export_shared_snapshot_index_design],
)
async def test_live_llm_drafts_are_not_available_over_public_links(exporter) -> None:
    """A bearer link must never trigger a paid external LLM request."""

    session = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await exporter(
            share_link_uuid=uuid.uuid4(),
            schema_snapshot_uuid=uuid.uuid4(),
            mode="llm-draft",
            session=session,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "unsupported public export mode"
    session.get.assert_not_awaited()


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
    assert out["error_message"] is None
    assert _SECRET_ERROR_MESSAGE not in payload
    assert _SECRET_RELATION_COMMENT not in payload
    assert _SECRET_COLUMN_COMMENT not in payload
    assert _SECRET_EXAMPLE_VALUE not in payload
    assert _SECRET_WRONG_PATH not in payload
    assert "future_private_metadata" not in payload
    assert "future_owner_email" not in payload
    assert out["snapshot_json"]["database_name"] == "public-demo-database"
    assert out["snapshot_json"]["schemas"] == [
        {"schema_oid": 10, "schema_name": "public"},
        "legacy_schema",
    ]


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


@pytest.mark.asyncio
async def test_shared_index_design_markdown_redacts_sensitive_fields() -> None:
    """Public index-design share export must not leak comments/example values."""

    session = _share_session(_sensitive_snapshot())
    share_uuid, snapshot_uuid = session._ids
    markdown = await export_shared_snapshot_index_design(
        share_link_uuid=share_uuid,
        schema_snapshot_uuid=snapshot_uuid,
        mode="markdown",
        session=session,
    )
    assert _SECRET_RELATION_COMMENT not in markdown
    assert _SECRET_COLUMN_COMMENT not in markdown
    assert _SECRET_EXAMPLE_VALUE not in markdown


@pytest.mark.asyncio
async def test_shared_sql_export_redacts_sensitive_fields() -> None:
    """Public SQL share export must not embed comments/example values."""

    session = _share_session(_sensitive_snapshot())
    share_uuid, snapshot_uuid = session._ids
    sql = await export_shared_snapshot_sql(
        share_link_uuid=share_uuid,
        schema_snapshot_uuid=snapshot_uuid,
        dialect="postgresql",
        session=session,
    )
    assert _SECRET_RELATION_COMMENT not in sql
    assert _SECRET_COLUMN_COMMENT not in sql
    assert _SECRET_EXAMPLE_VALUE not in sql
