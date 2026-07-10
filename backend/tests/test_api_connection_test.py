import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.api.connections import test_connection as run_connection_test
from app.auth import CurrentUser
from app.db_introspect import probe_database


def _user():
    return CurrentUser(
        user_account_uuid=uuid.uuid4(), subject="t", display_name="T"
    )


def _conn():
    return SimpleNamespace(dsn_ciphertext=b"ciphertext", dsn_nonce=b"nonce")


@pytest.mark.asyncio
async def test_test_connection_returns_404_when_missing():
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=None)  # no such connection
    with pytest.raises(HTTPException) as exc:
        await run_connection_test(
            db_connection_uuid=uuid.uuid4(), user=_user(), session=session
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_test_connection_masks_forbidden_as_404():
    # A non-member must not learn the connection exists (IDOR).
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=uuid.uuid4())
    with patch(
        "app.api.connections.require_project_member",
        new_callable=AsyncMock,
        side_effect=HTTPException(status_code=403, detail="denied"),
    ):
        with pytest.raises(HTTPException) as exc:
            await run_connection_test(
                db_connection_uuid=uuid.uuid4(), user=_user(), session=session
            )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_test_connection_reports_ok_true_on_success():
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=uuid.uuid4())
    session.get = AsyncMock(return_value=_conn())
    with patch(
        "app.api.connections.require_project_member", new_callable=AsyncMock
    ), patch(
        "app.api.connections.decrypt_text",
        return_value="postgresql://u@db.example.com/app",
    ), patch(
        "app.api.connections.probe_database",
        new_callable=AsyncMock,
        return_value="16.2",
    ):
        out = await run_connection_test(
            db_connection_uuid=uuid.uuid4(), user=_user(), session=session
        )
    assert out.ok is True
    assert out.server_version == "16.2"
    assert out.error is None


@pytest.mark.asyncio
async def test_test_connection_reports_ok_false_on_probe_failure():
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=uuid.uuid4())
    session.get = AsyncMock(return_value=_conn())
    with patch(
        "app.api.connections.require_project_member", new_callable=AsyncMock
    ), patch(
        "app.api.connections.decrypt_text",
        return_value="postgresql://u@db.example.com/app",
    ), patch(
        "app.api.connections.probe_database",
        new_callable=AsyncMock,
        side_effect=RuntimeError(
            "database host is not in the introspection allowlist"
        ),
    ):
        out = await run_connection_test(
            db_connection_uuid=uuid.uuid4(), user=_user(), session=session
        )
    assert out.ok is False
    assert out.server_version is None
    assert "allowlist" in (out.error or "")


@pytest.mark.asyncio
async def test_probe_database_routes_to_postgres():
    with patch(
        "app.db_introspect.probe_postgres",
        new_callable=AsyncMock,
        return_value="16.0",
    ):
        assert await probe_database("postgresql://u@db.example.com/app") == "16.0"


@pytest.mark.asyncio
async def test_probe_database_wraps_and_redacts_errors():
    dsn = "postgresql://user:s3cret@db.example.com/app"
    with patch(
        "app.db_introspect.probe_postgres",
        new_callable=AsyncMock,
        side_effect=OSError(f"could not connect to {dsn}"),
    ):
        with pytest.raises(RuntimeError) as exc:
            await probe_database(dsn)
    # Credentials must never surface in the wrapped error.
    assert "s3cret" not in str(exc.value)
