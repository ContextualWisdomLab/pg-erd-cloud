from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
import time
from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.settings import settings

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_TOKEN_TTL_SECONDS = 12 * 60 * 60
CSRF_TOKEN_NONCE_BYTES = 16


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


def _csrf_signature(secret: str, issued_at: str, nonce: str) -> bytes:
    message = f"{issued_at}.{nonce}".encode("ascii")
    return hmac.new(
        secret.encode("utf-8"),
        message,
        hashlib.sha256,
    ).digest()


def generate_csrf_token(secret: str, now: int | None = None) -> str:
    """Create a short-lived token signed with the application secret."""
    issued_at = str(int(time.time() if now is None else now))
    nonce = _base64url_encode(secrets.token_bytes(CSRF_TOKEN_NONCE_BYTES))
    signature = _base64url_encode(_csrf_signature(secret, issued_at, nonce))
    return f"{issued_at}.{nonce}.{signature}"


def verify_csrf_token(
    token: str,
    secret: str,
    ttl_seconds: int = CSRF_TOKEN_TTL_SECONDS,
    now: int | None = None,
) -> bool:
    """Validate a server-issued CSRF token without accepting caller entropy."""
    parts = token.split(".")
    if len(parts) != 3:
        return False

    issued_at, nonce, signature = parts
    current_time = int(time.time() if now is None else now)
    try:
        issued_at_int = int(issued_at)
        signature_bytes = _base64url_decode(signature)
    except (binascii.Error, ValueError):
        return False

    if (
        current_time - issued_at_int > ttl_seconds
        or issued_at_int > current_time
    ):
        return False

    expected = _csrf_signature(secret, issued_at, nonce)
    return hmac.compare_digest(signature_bytes, expected)


def make_csrf_middleware(
    route_prefix: str = "/api",
    header_name: str = CSRF_HEADER_NAME,
    token_secret: str | None = None,
    ttl_seconds: int = CSRF_TOKEN_TTL_SECONDS,
) -> Callable[
    [Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]
]:
    """Require a non-simple CSRF header for state-changing API requests."""

    async def middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Reject unsafe API requests that do not include a CSRF token."""
        if (
            request.method.upper() in SAFE_METHODS
            or not request.url.path.startswith(route_prefix)
        ):
            return await call_next(request)

        secret = settings.app_secret if token_secret is None else token_secret
        token = request.headers.get(header_name, "").strip()
        if not verify_csrf_token(token, secret, ttl_seconds=ttl_seconds):
            return JSONResponse(
                {"detail": "CSRF token required"},
                status_code=403,
            )

        return await call_next(request)

    return middleware
