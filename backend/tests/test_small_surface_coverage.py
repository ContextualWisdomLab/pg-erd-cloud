"""Coverage contracts for small API and runtime-configuration surfaces."""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from starlette.requests import Request

from app import hypercorn_config
from app.api import api_keys, auth_routes, dbml
from app.auth import CurrentUser
from app.schemas import ApiKeyCreateIn, DbmlConvertIn


class _ApiKeySession:
    """Minimal async session for API-key revocation behavior."""

    def __init__(self, key: object | None) -> None:
        self.key = key
        self.commit_calls = 0

    async def get(self, _model: object, _key_id: uuid.UUID) -> object | None:
        """Return the configured key record."""
        return self.key

    async def commit(self) -> None:
        """Record persistence of a newly revoked key."""
        self.commit_calls += 1


@pytest.mark.parametrize(
    ("raw_value", "default", "expected"),
    [("4", "2", 4), ("0", "2", 1), ("bad", "3", 3), ("bad", "also-bad", 1)],
)
def test_hypercorn_integer_environment_parser(
    monkeypatch: pytest.MonkeyPatch,
    raw_value: str,
    default: str,
    expected: int,
) -> None:
    """Parse worker counts with bounded fallbacks for malformed values."""
    monkeypatch.setenv("WORKER_TEST_VALUE", raw_value)

    assert hypercorn_config._int_env("WORKER_TEST_VALUE", default) == expected


def test_hypercorn_integer_environment_parser_uses_default_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use the supplied default when the environment variable is absent."""
    monkeypatch.delenv("WORKER_TEST_MISSING", raising=False)

    assert hypercorn_config._int_env("WORKER_TEST_MISSING", "5") == 5


@pytest.mark.asyncio
async def test_logout_revokes_current_request_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Delegate logout to the token-revocation boundary and return success."""
    request = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "https",
            "path": "/api/auth/logout",
            "raw_path": b"/api/auth/logout",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 443),
            "root_path": "",
        }
    )
    observed: list[Request] = []

    async def revoke(target: Request) -> None:
        observed.append(target)

    monkeypatch.setattr(auth_routes, "revoke_current_request_token", revoke)

    assert await auth_routes.logout(request) == {"ok": True}
    assert observed == [request]


@pytest.mark.asyncio
@pytest.mark.parametrize(("include_ddl", "expected_ddl"), [(False, None), (True, "CREATE TABLE")])
async def test_convert_dbml_maps_parser_output_and_optional_ddl(
    monkeypatch: pytest.MonkeyPatch,
    include_ddl: bool,
    expected_ddl: str | None,
) -> None:
    """Return deterministic table/FK counts and only generate requested DDL."""
    snapshot = {
        "relations": [{"name": "users"}, {"name": "orders"}],
        "fk_edges": [{"child": "orders", "parent": "users"}],
    }
    ddl_calls: list[tuple[dict[str, object], str]] = []
    monkeypatch.setattr(dbml, "parse_dbml", lambda _text: snapshot)

    def render_ddl(value: dict[str, object], *, target_dialect: str) -> str:
        ddl_calls.append((value, target_dialect))
        return "CREATE TABLE"

    monkeypatch.setattr(dbml, "snapshot_json_to_sql", render_ddl)
    user = CurrentUser(
        user_account_uuid=uuid.uuid4(),
        subject="oidc|buyer",
        display_name="Buyer",
    )

    result = await dbml.convert_dbml(
        DbmlConvertIn(dbml="Table users { id int }", include_ddl=include_ddl),
        user=user,
    )

    assert result.snapshot_json == snapshot
    assert result.ddl == expected_ddl
    assert result.tables == 2
    assert result.foreign_keys == 1
    assert ddl_calls == ([(snapshot, "postgresql")] if include_ddl else [])


@pytest.mark.asyncio
async def test_revoke_api_key_persists_first_revocation() -> None:
    """Set and commit a revocation timestamp when an owned key is still active."""
    user_account_uuid = uuid.uuid4()
    key_uuid = uuid.uuid4()
    key = type(
        "ApiKeyRecord",
        (),
        {
            "api_key_uuid": key_uuid,
            "user_account_uuid": user_account_uuid,
            "key_name": "buyer_key",
            "key_prefix": "pgerd_abc123",
            "created_at": dt.datetime(2026, 8, 7, tzinfo=dt.timezone.utc),
            "revoked_at": None,
        },
    )()
    session = _ApiKeySession(key)
    user = CurrentUser(
        user_account_uuid=user_account_uuid,
        subject="oidc|buyer",
        display_name="Buyer",
    )

    result = await api_keys.revoke_api_key(key_uuid, user=user, session=session)  # type: ignore[arg-type]

    assert session.commit_calls == 1
    assert key.revoked_at is not None
    assert result.api_key_uuid == key_uuid
    assert result.revoked_at == key.revoked_at


def test_api_key_create_schema_accepts_descriptive_name() -> None:
    """Keep the production API-key request schema exercised by direct tests."""
    assert ApiKeyCreateIn(key_name="buyer_access_key").key_name == "buyer_access_key"
