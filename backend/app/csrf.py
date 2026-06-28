from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
CSRF_HEADER_NAME = "X-CSRF-Token"
MIN_CSRF_TOKEN_LENGTH = 16


def make_csrf_middleware(
    route_prefix: str = "/api",
    header_name: str = CSRF_HEADER_NAME,
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

        token = request.headers.get(header_name, "").strip()
        if len(token) < MIN_CSRF_TOKEN_LENGTH:
            return JSONResponse(
                {"detail": "CSRF token required"},
                status_code=403,
            )

        return await call_next(request)

    return middleware
