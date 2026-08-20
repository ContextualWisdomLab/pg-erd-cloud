from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
REQUEST_BODY_TOO_LARGE_DETAIL = "request body too large"


def _declared_content_length(scope: Scope) -> int | None:
    """Return a valid non-negative Content-Length declaration when present."""

    for name, value in scope.get("headers", []):
        if name.lower() != b"content-length":
            continue
        try:
            length = int(value.decode("ascii"))
        except (UnicodeDecodeError, ValueError):
            return None
        return length if length >= 0 else None
    return None


def _is_limited_request(scope: Scope, route_prefix: str) -> bool:
    """Return whether an ASGI scope is an unsafe request in the bounded API tree."""

    if scope.get("type") != "http":
        return False
    if str(scope.get("method", "")).upper() not in UNSAFE_METHODS:
        return False
    path = str(scope.get("path", ""))
    return (
        route_prefix == "/"
        or path == route_prefix
        or path.startswith(f"{route_prefix}/")
    )


class RequestBodyLimitMiddleware:
    """Reject oversized unsafe API bodies before routing or model parsing.

    The middleware buffers at most ``max_body_bytes`` of an applicable request,
    rejecting both oversized declared lengths and chunked bodies before the
    downstream FastAPI application performs authentication or Pydantic parsing.
    Buffered ASGI messages are replayed unchanged for accepted requests.
    """

    def __init__(
        self,
        app: ASGIApp,
        max_body_bytes: int,
        route_prefix: str = "/api",
    ) -> None:
        """Wrap ``app`` with a positive byte limit for unsafe API requests."""

        if max_body_bytes < 1:
            raise ValueError("max_body_bytes must be positive")
        if not route_prefix.startswith("/"):
            raise ValueError("route_prefix must start with /")
        self.app = app
        self.max_body_bytes = max_body_bytes
        self.route_prefix = route_prefix.rstrip("/") or "/"

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Send the uniform HTTP 413 response without invoking the application."""

        response = JSONResponse(
            {"detail": REQUEST_BODY_TOO_LARGE_DETAIL},
            status_code=413,
        )
        await response(scope, receive, send)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Enforce the configured limit and replay accepted request messages."""

        if not _is_limited_request(scope, self.route_prefix):
            await self.app(scope, receive, send)
            return

        declared_length = _declared_content_length(scope)
        if declared_length is not None and declared_length > self.max_body_bytes:
            await self._reject(scope, receive, send)
            return

        buffered_messages: list[Message] = []
        received_bytes = 0
        while True:
            message = await receive()
            buffered_messages.append(message)
            if message["type"] == "http.disconnect":
                break
            if message["type"] != "http.request":
                continue
            received_bytes += len(message.get("body", b""))
            if received_bytes > self.max_body_bytes:
                await self._reject(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        message_index = 0

        async def replay_receive() -> Message:
            """Replay buffered messages, then delegate any later receive calls."""

            nonlocal message_index
            if message_index < len(buffered_messages):
                message = buffered_messages[message_index]
                message_index += 1
                return message
            return await receive()

        await self.app(scope, replay_receive, send)
