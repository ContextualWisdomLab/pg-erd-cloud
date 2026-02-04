from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import Response

_DOCS_PREFIXES: tuple[str, ...] = (
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/openapi.json",
)


def _is_https(request: Request) -> bool:
    xfp = request.headers.get("X-Forwarded-Proto")
    if xfp and xfp.lower() == "https":
        return True
    return request.url.scheme.lower() == "https"


def _should_apply_csp(request: Request) -> bool:
    path = request.url.path
    return not any(path.startswith(p) for p in _DOCS_PREFIXES)


def apply_security_headers(request: Request, response: Response) -> None:
    """Apply baseline response hardening headers.

    Notes:
    - Prefer setting headers at the ingress/reverse-proxy for production.
    - We also apply them in-app as a fallback so local/dev/test runs match
      production expectations.
    - CSP is intentionally not applied to FastAPI docs endpoints by default to
      avoid breaking Swagger UI.
    """

    def _set_if_missing(name: str, value: str) -> None:
        if name not in response.headers:
            response.headers[name] = value

    _set_if_missing("X-Content-Type-Options", "nosniff")
    _set_if_missing("X-Frame-Options", "DENY")
    _set_if_missing("Referrer-Policy", "no-referrer")
    _set_if_missing(
        "Permissions-Policy",
        "geolocation=(), microphone=(), camera=()",
    )

    if _should_apply_csp(request):
        # API-first default. We only need a minimal policy for JSON responses.
        # (Swagger UI is excluded by _DOCS_PREFIXES.)
        _set_if_missing(
            "Content-Security-Policy",
            "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
            "form-action 'none'",
        )

    if _is_https(request):
        # HSTS is only meaningful over HTTPS.
        _set_if_missing(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )


def make_security_headers_middleware() -> (
    Callable[
        [Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]
    ]
):
    """Create a Starlette/FastAPI http middleware applying response headers."""

    async def middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        apply_security_headers(request, response)
        return response

    return middleware
