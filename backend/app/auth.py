from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Any, cast

import httpx
from fastapi import Depends, HTTPException, Request
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import UserAccount
from app.settings import settings


def _parse_oidc_algorithms(raw: str) -> list[str]:
    """Parse OIDC_ALGORITHMS into a non-empty allowlist.

    Security note:
    - JWT verification must *not* trust the token header's `alg`.
    - We pass an explicit allowlist to the verifier.
    """

    # Normalize and deduplicate so env values like "rs256, RS256" behave
    # predictably.
    normalized: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        alg = part.strip().upper()
        if not alg:
            continue
        # Defensive: never allow unsigned tokens.
        if alg == "NONE":
            continue
        if alg in seen:
            continue
        seen.add(alg)
        normalized.append(alg)

    return normalized or ["RS256"]


@dataclass(frozen=True)
class CurrentUser:
    """Authenticated user identity used by API handlers."""

    user_account_uuid: uuid.UUID
    subject: str
    display_name: str | None


_oidc_config: dict[str, Any] | None = None
_oidc_jwks: dict[str, Any] | None = None
_oidc_expires_at: dt.datetime = dt.datetime.fromtimestamp(0, tz=dt.timezone.utc)


async def _get_oidc_config() -> dict:
    """Fetch and cache the OIDC discovery document."""
    if not settings.oidc_issuer:
        raise RuntimeError("OIDC is disabled")

    global _oidc_config, _oidc_expires_at
    now = dt.datetime.now(dt.timezone.utc)
    if _oidc_config is not None and now < _oidc_expires_at:
        return cast(dict, _oidc_config)

    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.get(
            f"{settings.oidc_issuer.rstrip('/')}/.well-known/openid-configuration"
        )
        r.raise_for_status()
        config = cast(dict[str, Any], r.json())

    _oidc_config = config
    _oidc_expires_at = now + dt.timedelta(minutes=10)
    return cast(dict, config)


async def _get_jwks() -> dict:
    """Fetch and cache the OIDC JWKS (signing keys)."""
    config = await _get_oidc_config()
    jwks_uri = config.get("jwks_uri")
    if not isinstance(jwks_uri, str):
        raise RuntimeError("OIDC jwks_uri missing")

    global _oidc_jwks, _oidc_expires_at
    # Share same TTL as config.
    now = dt.datetime.now(dt.timezone.utc)
    if _oidc_jwks is not None and now < _oidc_expires_at:
        return cast(dict, _oidc_jwks)

    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.get(jwks_uri)
        r.raise_for_status()
        jwks = cast(dict[str, Any], r.json())
    _oidc_jwks = jwks
    return cast(dict, jwks)


def _pick_jwk(jwks: dict, kid: str | None) -> dict | None:
    """Pick a JWK from a JWKS set by kid (or first if kid is None)."""
    keys = jwks.get("keys")
    if not isinstance(keys, list):
        return None
    for k in keys:
        if not isinstance(k, dict):
            continue
        if kid is None or k.get("kid") == kid:
            return k
    return None


async def _get_subject_from_request(request: Request) -> tuple[str, str | None]:
    """Extract (subject, display_name) from a request.

    Uses OIDC bearer tokens when configured; otherwise falls back to a dev
    header for local development.
    """

    # OIDC mode (Casdoor etc.)
    if settings.oidc_issuer:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        token = auth.split(" ", 1)[1].strip()
        try:
            header = jwt.get_unverified_header(token)
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=401, detail="invalid token header")

        header_alg_raw = header.get("alg")
        if not isinstance(header_alg_raw, str) or not header_alg_raw:
            raise HTTPException(status_code=401, detail="token missing alg")

        # Normalize so equivalent-case values (e.g. "rs256" vs "RS256") don't
        # fail the allowlist check.
        header_alg = header_alg_raw.upper()

        allowed_algs = _parse_oidc_algorithms(settings.oidc_algorithms)
        if header_alg not in allowed_algs:
            raise HTTPException(
                status_code=401,
                detail=f"token algorithm not allowed: {header_alg_raw}",
            )

        jwks = await _get_jwks()
        jwk = _pick_jwk(jwks, header.get("kid"))
        if jwk is None:
            raise HTTPException(status_code=401, detail="unknown signing key")

        try:
            claims = jwt.decode(
                token,
                jwk,
                algorithms=allowed_algs,
                audience=settings.oidc_audience,
                issuer=settings.oidc_issuer,
                options={"verify_aud": bool(settings.oidc_audience)},
            )
        except Exception as err:
            raise HTTPException(
                status_code=401, detail="token verification failed"
            ) from err

        sub = claims.get("sub")
        name = claims.get("name") or claims.get("preferred_username")
        if not isinstance(sub, str):
            raise HTTPException(status_code=401, detail="token missing sub")
        return sub, str(name) if isinstance(name, str) else None

    # Dev fallback (no OIDC configured)
    dev_user = request.headers.get("X-Dev-User") or "local"
    dev_user = dev_user.strip()[:128]
    return f"dev:{dev_user}", dev_user


async def _ensure_user(
    session: AsyncSession, subject: str, display_name: str | None
) -> CurrentUser:
    """Get or create a UserAccount for the given OIDC subject."""
    row = await session.execute(
        select(UserAccount).where(UserAccount.oidc_subject == subject)
    )
    existing = row.scalars().first()
    if existing is not None:
        return CurrentUser(
            user_account_uuid=existing.user_account_uuid,
            subject=existing.oidc_subject,
            display_name=existing.display_name,
        )

    user = UserAccount(
        user_account_uuid=uuid.uuid4(),
        oidc_subject=subject,
        display_name=display_name,
        created_at=dt.datetime.now(dt.timezone.utc),
    )
    session.add(user)
    await session.flush()
    return CurrentUser(
        user_account_uuid=user.user_account_uuid,
        subject=user.oidc_subject,
        display_name=user.display_name,
    )


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    """FastAPI dependency that authenticates and returns the current user."""
    subject, display_name = await _get_subject_from_request(request)
    async with session.begin():
        return await _ensure_user(session, subject, display_name)
