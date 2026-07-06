from __future__ import annotations

import datetime as dt
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import API_KEY_PREFIX, CurrentUser, get_current_user, hash_api_key
from app.db import get_read_session, get_session
from app.models import ApiKey
from app.sanitize import sanitize_for_storage
from app.schemas import ApiKeyCreatedOut, ApiKeyCreateIn, ApiKeyOut

router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])


def _to_out(key: ApiKey) -> ApiKeyOut:
    return ApiKeyOut(
        api_key_uuid=key.api_key_uuid,
        key_name=key.key_name,
        key_prefix=key.key_prefix,
        created_at=key.created_at,
        revoked_at=key.revoked_at,
    )


@router.get("", response_model=list[ApiKeyOut])
async def list_api_keys(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> list[ApiKeyOut]:
    """List the caller's API keys (never the secrets)."""
    rows = await session.execute(
        select(ApiKey)
        .where(ApiKey.user_account_uuid == user.user_account_uuid)
        .order_by(ApiKey.created_at.desc())
    )
    return [_to_out(k) for k in rows.scalars().all()]


@router.post("", response_model=ApiKeyCreatedOut)
async def create_api_key(
    body: ApiKeyCreateIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiKeyCreatedOut:
    """Create an API key. The secret is returned ONCE and never stored.

    Only its SHA-256 hash is persisted; ``key_prefix`` lets the user recognize
    the key later without exposing it.
    """
    token = API_KEY_PREFIX + secrets.token_urlsafe(32)
    key = ApiKey(
        api_key_uuid=uuid.uuid4(),
        user_account_uuid=user.user_account_uuid,
        key_name=str(sanitize_for_storage(body.key_name)),
        key_hash=hash_api_key(token),
        key_prefix=token[: len(API_KEY_PREFIX) + 6],
        created_at=dt.datetime.now(dt.timezone.utc),
        revoked_at=None,
    )
    session.add(key)
    await session.commit()
    return ApiKeyCreatedOut(
        api_key_uuid=key.api_key_uuid,
        key_name=key.key_name,
        key_prefix=key.key_prefix,
        created_at=key.created_at,
        revoked_at=None,
        secret=token,
    )


@router.delete("/{api_key_uuid}", response_model=ApiKeyOut)
async def revoke_api_key(
    api_key_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ApiKeyOut:
    """Revoke an API key (idempotent; keeps the row for auditability).

    IDOR-safe: another user's key yields the same uniform 404 as a missing one.
    """
    key = await session.get(ApiKey, api_key_uuid)
    if key is None or key.user_account_uuid != user.user_account_uuid:
        raise HTTPException(status_code=404, detail="api key not found")
    if key.revoked_at is None:
        key.revoked_at = dt.datetime.now(dt.timezone.utc)
        await session.commit()
    return _to_out(key)
