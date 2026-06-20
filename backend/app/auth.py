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


@dataclass(frozen=True)
class VerifiedToken:
    """Verified OIDC token details needed by auth and logout flows."""

    subject: str
    display_name: str | None
    jwt_id: str
    expires_at: dt.datetime


_oidc_config: dict[str, Any] | None = None
_oidc_jwks: dict[str, Any] | None = None
_oidc_expires_at: dt.datetime = dt.datetime.fromtimestamp(0, tz=dt.timezone.utc)
OIDC_ALLOWED_ALGORITHMS = tuple(_parse_oidc_algorithms(settings.oidc_algorithms))
_revoked_token_jtis: dict[str, dt.datetime] = {}


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


def _jwt_expiry(claims: dict[str, Any]) -> dt.datetime:
    """Return the JWT expiry as an aware UTC datetime."""

    exp = claims.get("exp")
    if not isinstance(exp, int | float):
        raise HTTPException(status_code=401, detail="token missing exp")
    return dt.datetime.fromtimestamp(float(exp), tz=dt.timezone.utc)


def _prune_revoked_token_jtis(now: dt.datetime | None = None) -> None:
    """Drop expired token revocation entries from the in-memory cache."""

    current = now or dt.datetime.now(dt.timezone.utc)
    expired = [
        jwt_id
        for jwt_id, expires_at in _revoked_token_jtis.items()
        if expires_at <= current
    ]
    for jwt_id in expired:
        _revoked_token_jtis.pop(jwt_id, None)


def revoke_token_jti(jwt_id: str, expires_at: dt.datetime) -> None:
    """Record a JWT ID as revoked until its natural expiry."""

    if not jwt_id:
        return
    _prune_revoked_token_jtis()
    _revoked_token_jtis[jwt_id] = expires_at


def is_token_jti_revoked(jwt_id: str) -> bool:
    """Return whether the JWT ID is currently revoked."""

    _prune_revoked_token_jtis()
    return jwt_id in _revoked_token_jtis


async def _get_verified_token_from_request(request: Request) -> VerifiedToken:
    """Extract and verify OIDC token claims from a request.

    Uses OIDC bearer tokens when configured. If OIDC is not configured, auth
    fails closed.
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

        if header_alg not in OIDC_ALLOWED_ALGORITHMS:
            raise HTTPException(
                status_code=401,
                detail="unsupported token algorithm",
            )

        jwks = await _get_jwks()
        jwk = _pick_jwk(jwks, header.get("kid"))
        if jwk is None:
            raise HTTPException(status_code=401, detail="unknown signing key")

        try:
            claims = jwt.decode(
                token,
                jwk,
                algorithms=list(OIDC_ALLOWED_ALGORITHMS),
                audience=settings.oidc_audience,
                issuer=settings.oidc_issuer,
                options={
                    "verify_aud": bool(settings.oidc_audience),
                    "require_exp": True,
                    "require_jti": True,
                },
            )
        except Exception as err:
            raise HTTPException(
                status_code=401, detail="token verification failed"
            ) from err

        sub = claims.get("sub")
        jwt_id = claims.get("jti")
        name = claims.get("name") or claims.get("preferred_username")
        if not isinstance(sub, str):
            raise HTTPException(status_code=401, detail="token missing sub")
        if not isinstance(jwt_id, str) or not jwt_id.strip():
            raise HTTPException(status_code=401, detail="token missing jti")
        expires_at = _jwt_expiry(cast(dict[str, Any], claims))
        if is_token_jti_revoked(jwt_id):
            raise HTTPException(status_code=401, detail="token revoked")
        return VerifiedToken(
            subject=sub,
            display_name=str(name) if isinstance(name, str) else None,
            jwt_id=jwt_id,
            expires_at=expires_at,
        )

    raise HTTPException(status_code=500, detail="OIDC configuration required")


async def _get_subject_from_request(request: Request) -> tuple[str, str | None]:
    """Extract (subject, display_name) from a verified request token."""

    verified = await _get_verified_token_from_request(request)
    return verified.subject, verified.display_name


async def try_get_subject_for_rate_limit(request: Request) -> str | None:
    """Best-effort subject extraction for rate limiting.

    This helper is intentionally lightweight:
    - It must NOT touch the DB (unlike get_current_user).
    - It must NOT change auth behavior. Missing/invalid auth returns None so
      unauthenticated requests can still be limited by IP.
    """

    try:
        subject, _ = await _get_subject_from_request(request)
        return subject
    except HTTPException:
        return None


_user_cache: dict[str, tuple[CurrentUser, dt.datetime]] = {}
USER_CACHE_MAX_SIZE = 1000
USER_CACHE_TTL = dt.timedelta(minutes=5)


async def _ensure_user(
    session: AsyncSession, subject: str, display_name: str | None
) -> CurrentUser:
    """Get or create a UserAccount for the given OIDC subject."""
    now = dt.datetime.now(dt.timezone.utc)
    cached = _user_cache.get(subject)
    if cached is not None:
        user, expires_at = cached
        if now < expires_at:
            return user
        else:
            del _user_cache[subject]

    row = await session.execute(
        select(UserAccount).where(UserAccount.oidc_subject == subject)
    )
    existing = row.scalars().first()
    if existing is not None:
        user = CurrentUser(
            user_account_uuid=existing.user_account_uuid,
            subject=existing.oidc_subject,
            display_name=existing.display_name,
        )
    else:
        user_account = UserAccount(
            user_account_uuid=uuid.uuid4(),
            oidc_subject=subject,
            display_name=display_name,
            created_at=now,
        )
        session.add(user_account)
        await session.flush()
        user = CurrentUser(
            user_account_uuid=user_account.user_account_uuid,
            subject=user_account.oidc_subject,
            display_name=user_account.display_name,
        )

    if len(_user_cache) >= USER_CACHE_MAX_SIZE:
        _user_cache.clear()

    _user_cache[subject] = (user, now + USER_CACHE_TTL)
    return user


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    """FastAPI dependency that authenticates and returns the current user."""
    subject, display_name = await _get_subject_from_request(request)
    async with session.begin():
        return await _ensure_user(session, subject, display_name)


async def revoke_current_request_token(request: Request) -> None:
    """Revoke the current request token until its natural expiry."""

    verified = await _get_verified_token_from_request(request)
    revoke_token_jti(verified.jwt_id, verified.expires_at)
