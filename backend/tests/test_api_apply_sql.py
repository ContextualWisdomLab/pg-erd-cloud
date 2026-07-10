import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.api.connections import apply_sql
from app.auth import CurrentUser
from app.db_introspect import apply_database_sql
from app.schemas import ApplySqlIn


def _user():
    return CurrentUser(user_account_uuid=uuid.uuid4(), subject="t", display_name="T")


def _conn():
    return SimpleNamespace(dsn_ciphertext=b"c", dsn_nonce=b"n")


def _body(dry_run=True):
    return ApplySqlIn(sql="CREATE TABLE safe_table (id bigint);", dry_run=dry_run)


@pytest.mark.asyncio
async def test_apply_sql_returns_404_when_missing():
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as e:
        await apply_sql(db_connection_uuid=uuid.uuid4(), body=_body(), user=_user(), session=session)
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_apply_sql_masks_non_member_as_404():
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=uuid.uuid4())
    with patch(
        "app.api.connections.require_project_member",
        new_callable=AsyncMock,
        side_effect=HTTPException(status_code=403, detail="project access denied"),
    ):
        with pytest.raises(HTTPException) as e:
            await apply_sql(db_connection_uuid=uuid.uuid4(), body=_body(), user=_user(), session=session)
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_apply_sql_returns_403_when_member_lacks_editor():
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=uuid.uuid4())
    # first call (membership) passes, second call (editor) raises 403
    with patch(
        "app.api.connections.require_project_member",
        new_callable=AsyncMock,
        side_effect=[None, HTTPException(status_code=403, detail="insufficient project role")],
    ):
        with pytest.raises(HTTPException) as e:
            await apply_sql(db_connection_uuid=uuid.uuid4(), body=_body(), user=_user(), session=session)
    assert e.value.status_code == 403


@pytest.mark.asyncio
async def test_apply_sql_reports_ok_true_on_success():
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=uuid.uuid4())
    session.get = AsyncMock(return_value=_conn())
    with patch(
        "app.api.connections.require_project_member", new_callable=AsyncMock
    ), patch(
        "app.api.connections.decrypt_text", return_value="postgresql://u@db.example.com/x"
    ), patch(
        "app.api.connections.apply_database_sql", new_callable=AsyncMock
    ) as apply_mock:
        out = await apply_sql(
            db_connection_uuid=uuid.uuid4(), body=_body(dry_run=True), user=_user(), session=session
        )
    assert out.ok is True and out.dry_run is True and out.error is None
    apply_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_sql_reports_ok_false_on_error():
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=uuid.uuid4())
    session.get = AsyncMock(return_value=_conn())
    with patch(
        "app.api.connections.require_project_member", new_callable=AsyncMock
    ), patch(
        "app.api.connections.decrypt_text", return_value="postgresql://u@db.example.com/x"
    ), patch(
        "app.api.connections.apply_database_sql",
        new_callable=AsyncMock,
        side_effect=RuntimeError("syntax error at or near"),
    ):
        out = await apply_sql(
            db_connection_uuid=uuid.uuid4(), body=_body(dry_run=False), user=_user(), session=session
        )
    assert out.ok is False and out.dry_run is False and "syntax error" in (out.error or "")


@pytest.mark.asyncio
async def test_apply_database_sql_rejects_non_postgres():
    with pytest.raises(RuntimeError):
        await apply_database_sql(
            "snowflake://u@acct/db", "CREATE TABLE safe_table (id int);"
        )


@pytest.mark.asyncio
async def test_apply_database_sql_routes_postgres_and_redacts():
    with patch("app.db_introspect.apply_postgres_ddl", new_callable=AsyncMock) as m:
        await apply_database_sql(
            "postgresql://u@db.example.com/x",
            "CREATE TABLE safe_table (id int);",
            dry_run=True,
        )
    m.assert_awaited_once()
    assert m.await_args.args[1].sql == "CREATE TABLE safe_table (id int);"
    with patch(
        "app.db_introspect.apply_postgres_ddl",
        new_callable=AsyncMock,
        side_effect=OSError("connect to postgresql://user:s3cret@db"),
    ):
        with pytest.raises(RuntimeError) as e:
            await apply_database_sql(
                "postgresql://user:s3cret@db.example.com/x",
                "CREATE TABLE safe_table (id int);",
            )
    assert "s3cret" not in str(e.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("sql", "expected_error"),
    [
        ("SELECT 1;", "SELECT is not allowed"),
        ("DROP TABLE user_account;", "DROP is not allowed"),
        (
            "CREATE TABLE bad_table (id bigint DEFAULT now());",
            "DEFAULT is not allowed",
        ),
        (
            'CREATE TABLE "BadTable" (id bigint);',
            "quoted literals and quoted identifiers are not allowed",
        ),
        (
            "CREATE TABLE BadTable (id bigint);",
            "table identifier must be unquoted snake_case",
        ),
        (
            "CREATE TABLE safe_table (id bigint); -- comment",
            "comments are not allowed",
        ),
    ],
)
async def test_apply_database_sql_rejects_unsafe_forward_ddl(
    sql: str, expected_error: str
):
    with patch("app.db_introspect.apply_postgres_ddl", new_callable=AsyncMock) as m:
        with pytest.raises(RuntimeError) as e:
            await apply_database_sql("postgresql://user:s3cret@db.example.com/x", sql)
    m.assert_not_awaited()
    assert expected_error in str(e.value)
    assert "s3cret" not in str(e.value)
