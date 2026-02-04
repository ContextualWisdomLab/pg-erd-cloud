from __future__ import annotations

from collections.abc import Mapping

from starlette.responses import Response

# NOTE: Keep this list intentionally small and API-safe.
# - Avoid CSP defaults here because it can break Swagger UI (/docs) unless
#   carefully scoped.
# - Prefer setting stronger policies at ingress/proxy where appropriate.
_DEFAULT_SECURITY_HEADERS: Mapping[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


def apply_security_headers(response: Response) -> None:
    """Apply a conservative set of security response headers.

    This function is side-effectful (mutates response.headers) but safe to call
    multiple times.
    """

    for name, value in _DEFAULT_SECURITY_HEADERS.items():
        # Don't override headers set by upstream proxies or specific routes.
        response.headers.setdefault(name, value)
