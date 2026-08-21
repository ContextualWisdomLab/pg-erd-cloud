import datetime as dt
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from app.api.api_keys import create_api_key, list_api_keys, revoke_api_key
from app.auth import (
    API_KEY_PBKDF2_ITERATIONS,
    API_KEY_PREFIX,
    CurrentUser,
    _user_from_api_key,
    hash_api_key,
)
from app.schemas import ApiKeyCreateIn


def _user(uid=None):
    return CurrentUser(
        user_account_uuid=uid or uuid.uuid4(), subject="t", display_name="T"
    )


def test_hash_is_deterministic_and_not_reversible():
    token = API_KEY_PREFIX + "abc123"
    assert hash_api_key(token) == hash_api_key(token)
    assert token not in hash_api_key(token)
    assert len(hash_api_key(token)) == 64  # pbkdf2-hmac-sha256 hex
    assert API_KEY_PBKDF2_ITERATIONS >= 200_000


@pytest.mark.asyncio
async def test_create_returns_secret_once_and_stores_only_hash():
    session = AsyncMock()
    session.add = Mock()
    user = _user()
    out = await create_api_key(
        body=ApiKeyCreateIn(key_name="ci"), user=user, session=session
    )
    assert out.secret.startswith(API_KEY_PREFIX)
    added = session.add.call_args[0][0]
    assert added.key_hash == hash_api_key(out.secret)
    assert out.secret not in (added.key_hash, added.key_prefix, added.key_name)
    assert out.key_prefix == out.secret[: len(API_KEY_PREFIX) + 6]


@pytest.mark.asyncio
async def test_auth_accepts_valid_key_and_rejects_revoked_or_unknown():
    token = API_KEY_PREFIX + "secret"
    account = SimpleNamespace(
        user_account_uuid=uuid.uuid4(), oidc_subject="dev:x", display_name="X"
    )
    live_key = SimpleNamespace(revoked_at=None)

    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=SimpleNamespace(first=lambda: (live_key, account))
    )
    user = await _user_from_api_key(session, token)
    assert user.user_account_uuid == account.user_account_uuid

    # revoked
    revoked_key = SimpleNamespace(revoked_at=dt.datetime.now(dt.timezone.utc))
    session.execute = AsyncMock(
        return_value=SimpleNamespace(first=lambda: (revoked_key, account))
    )
    with pytest.raises(HTTPException) as e:
        await _user_from_api_key(session, token)
    assert e.value.status_code == 401

    # unknown
    session.execute = AsyncMock(return_value=SimpleNamespace(first=lambda: None))
    with pytest.raises(HTTPException) as e2:
        await _user_from_api_key(session, token)
    assert e2.value.status_code == 401


@pytest.mark.asyncio
async def test_revoke_is_idor_safe_and_idempotent():
    owner = _user()
    other_key = SimpleNamespace(
        user_account_uuid=uuid.uuid4(),  # someone else's
        revoked_at=None,
    )
    session = AsyncMock()
    session.get = AsyncMock(return_value=other_key)
    with pytest.raises(HTTPException) as e:
        await revoke_api_key(api_key_uuid=uuid.uuid4(), user=owner, session=session)
    assert e.value.status_code == 404  # uniform: same as missing

    session.get = AsyncMock(return_value=None)
    with pytest.raises(HTTPException):
        await revoke_api_key(api_key_uuid=uuid.uuid4(), user=owner, session=session)

    # own key: revokes once, second call keeps timestamp (idempotent)
    ts = dt.datetime.now(dt.timezone.utc)
    own = SimpleNamespace(
        api_key_uuid=uuid.uuid4(),
        user_account_uuid=owner.user_account_uuid,
        key_name="ci", key_prefix="pgerd_abc", created_at=ts, revoked_at=ts,
    )
    session.get = AsyncMock(return_value=own)
    out = await revoke_api_key(api_key_uuid=own.api_key_uuid, user=owner, session=session)
    assert out.revoked_at == ts
    session.commit.assert_not_awaited()  # already revoked -> no write


@pytest.mark.asyncio
async def test_list_returns_only_metadata():
    user = _user()
    key = SimpleNamespace(
        api_key_uuid=uuid.uuid4(), key_name="ci", key_prefix="pgerd_abc",
        created_at=dt.datetime.now(dt.timezone.utc), revoked_at=None,
    )
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [key]))
    )
    out = await list_api_keys(user=user, session=session)
    assert len(out) == 1
    assert not hasattr(out[0], "secret")
