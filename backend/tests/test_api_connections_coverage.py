"""Boundary coverage for connection authorization and missing-row handling."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.api import connections
from app.auth import CurrentUser
from app.schemas import ApplySqlIn


class _Session:
    """Minimal async session with one project scalar and one connection lookup."""

    def __init__(self, project_space_uuid: uuid.UUID, connection: object | None = None) -> None:
        self.project_space_uuid = project_space_uuid
        self.connection = connection

    async def scalar(self, _statement: object) -> uuid.UUID:
        """Return the owning project identifier."""
        return self.project_space_uuid

    async def get(self, _model: object, _key: uuid.UUID) -> object | None:
        """Return the configured connection record."""
        return self.connection


def _user() -> CurrentUser:
    """Return one authenticated connection caller."""
    return CurrentUser(
        user_account_uuid=uuid.uuid4(),
        subject="oidc|connection-user",
        display_name="Connection User",
    )


@pytest.mark.asyncio
async def test_apply_sql_preserves_non_forbidden_authorization_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only a 403 membership denial is normalized to a hidden 404."""
    project_uuid = uuid.uuid4()

    async def unavailable(*_args: object, **_kwargs: object) -> None:
        raise HTTPException(status_code=503, detail="authorization unavailable")

    monkeypatch.setattr(connections, "require_project_member", unavailable)

    with pytest.raises(HTTPException) as exc_info:
        await connections.apply_sql(
            uuid.uuid4(),
            ApplySqlIn(sql="CREATE TABLE buyer_record (record_id integer)", dry_run=True),
            user=_user(),
            session=_Session(project_uuid),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "authorization unavailable"


@pytest.mark.asyncio
async def test_apply_sql_hides_connection_removed_after_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return the uniform 404 when the connection row disappears after membership lookup."""
    project_uuid = uuid.uuid4()

    async def member(*_args: object, **_kwargs: object) -> str:
        return "editor"

    monkeypatch.setattr(connections, "require_project_member", member)

    with pytest.raises(HTTPException) as exc_info:
        await connections.apply_sql(
            uuid.uuid4(),
            ApplySqlIn(sql="CREATE TABLE buyer_record (record_id integer)", dry_run=True),
            user=_user(),
            session=_Session(project_uuid, None),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "connection not found"


@pytest.mark.asyncio
async def test_connection_probe_preserves_non_forbidden_authorization_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Propagate non-403 authorization failures instead of disguising them as missing data."""
    project_uuid = uuid.uuid4()

    async def unavailable(*_args: object, **_kwargs: object) -> None:
        raise HTTPException(status_code=503, detail="authorization unavailable")

    monkeypatch.setattr(connections, "require_project_member", unavailable)

    with pytest.raises(HTTPException) as exc_info:
        await connections.test_connection(
            uuid.uuid4(),
            user=_user(),
            session=_Session(project_uuid),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "authorization unavailable"


@pytest.mark.asyncio
async def test_connection_probe_hides_connection_removed_after_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return the uniform 404 when an authorized connection lookup yields no row."""
    project_uuid = uuid.uuid4()

    async def member(*_args: object, **_kwargs: object) -> str:
        return "viewer"

    monkeypatch.setattr(connections, "require_project_member", member)

    with pytest.raises(HTTPException) as exc_info:
        await connections.test_connection(
            uuid.uuid4(),
            user=_user(),
            session=_Session(project_uuid, None),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "connection not found"
