from __future__ import annotations

import json
from collections.abc import Sequence

import pytest
from starlette.types import Message, Receive, Scope, Send

from app.request_body_limit import (
    REQUEST_BODY_TOO_LARGE_DETAIL,
    RequestBodyLimitMiddleware,
    _declared_content_length,
    _is_limited_request,
)


def _scope(
    *,
    method: str = "POST",
    path: str = "/api/items",
    headers: Sequence[tuple[bytes, bytes]] = (),
    scope_type: str = "http",
) -> Scope:
    """Build the minimal ASGI scope required by the middleware tests."""

    return {
        "type": scope_type,
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "root_path": "",
        "headers": list(headers),
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
    }  # type: ignore[return-value]


async def _run(
    middleware: RequestBodyLimitMiddleware,
    scope: Scope,
    messages: list[Message],
) -> list[Message]:
    """Execute an ASGI middleware instance and return every emitted message."""

    pending = list(messages)
    sent: list[Message] = []

    async def receive() -> Message:
        if pending:
            return pending.pop(0)
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        sent.append(message)

    await middleware(scope, receive, send)
    return sent


def test_request_body_limit_configuration_is_fail_closed() -> None:
    """Reject non-positive limits and malformed route prefixes."""

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        del scope, receive, send

    with pytest.raises(ValueError, match="positive"):
        RequestBodyLimitMiddleware(app, 0)
    with pytest.raises(ValueError, match="start with"):
        RequestBodyLimitMiddleware(app, 1, route_prefix="api")


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ([], None),
        ([(b"Content-Length", b"8")], 8),
        ([(b"content-length", b"-1")], None),
        ([(b"content-length", b"invalid")], None),
        ([(b"content-length", b"\xff")], None),
    ],
)
def test_declared_content_length_parsing(
    headers: list[tuple[bytes, bytes]], expected: int | None
) -> None:
    """Accept only non-negative ASCII Content-Length declarations."""

    assert _declared_content_length(_scope(headers=headers)) == expected


def test_limited_request_selection_is_bounded_to_unsafe_api_calls() -> None:
    """Limit unsafe API paths without intercepting other ASGI traffic."""

    assert _is_limited_request(_scope(), "/api") is True
    assert _is_limited_request(_scope(path="/api"), "/api") is True
    assert _is_limited_request(_scope(method="GET"), "/api") is False
    assert _is_limited_request(_scope(path="/apiary"), "/api") is False
    assert _is_limited_request(_scope(scope_type="websocket"), "/api") is False


@pytest.mark.asyncio
async def test_declared_oversize_is_rejected_before_downstream_execution() -> None:
    """Reject a known oversized body without invoking the protected app."""

    downstream_called = False

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal downstream_called
        downstream_called = True
        del scope, receive, send

    middleware = RequestBodyLimitMiddleware(app, 4)
    sent = await _run(
        middleware,
        _scope(headers=[(b"content-length", b"5")]),
        [{"type": "http.request", "body": b"12345", "more_body": False}],
    )

    assert downstream_called is False
    assert sent[0] == {
        "type": "http.response.start",
        "status": 413,
        "headers": [(b"content-length", b"35"), (b"content-type", b"application/json")],
    }
    assert json.loads(sent[1]["body"]) == {
        "detail": REQUEST_BODY_TOO_LARGE_DETAIL
    }


@pytest.mark.asyncio
async def test_chunked_body_is_bounded_and_replayed_without_changes() -> None:
    """Allow an exact-limit chunked body and replay all messages in order."""

    observed: list[Message] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        del scope
        observed.append(await receive())
        observed.append(await receive())
        observed.append(await receive())
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = RequestBodyLimitMiddleware(app, 4)
    sent = await _run(
        middleware,
        _scope(headers=[(b"content-length", b"invalid")]),
        [
            {"type": "http.request", "body": b"12", "more_body": True},
            {"type": "http.request", "body": b"34", "more_body": False},
            {"type": "http.disconnect"},
        ],
    )

    assert observed == [
        {"type": "http.request", "body": b"12", "more_body": True},
        {"type": "http.request", "body": b"34", "more_body": False},
        {"type": "http.disconnect"},
    ]
    assert sent[0]["status"] == 204


@pytest.mark.asyncio
async def test_streamed_oversize_is_rejected_without_downstream_execution() -> None:
    """Reject a body that exceeds the limit across multiple receive messages."""

    downstream_called = False

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal downstream_called
        downstream_called = True
        del scope, receive, send

    middleware = RequestBodyLimitMiddleware(app, 4)
    sent = await _run(
        middleware,
        _scope(),
        [
            {"type": "http.request", "body": b"123", "more_body": True},
            {"type": "http.request", "body": b"45", "more_body": False},
        ],
    )

    assert downstream_called is False
    assert sent[0]["status"] == 413


@pytest.mark.asyncio
async def test_disconnect_and_non_request_messages_are_replayed() -> None:
    """Preserve unusual ASGI messages instead of manufacturing request data."""

    observed: list[Message] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        del scope
        observed.append(await receive())
        observed.append(await receive())
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = RequestBodyLimitMiddleware(app, 4)
    sent = await _run(
        middleware,
        _scope(),
        [{"type": "test.message"}, {"type": "http.disconnect"}],
    )

    assert observed == [{"type": "test.message"}, {"type": "http.disconnect"}]
    assert sent[0]["status"] == 204


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scope",
    [
        _scope(method="GET"),
        _scope(path="/healthz"),
        _scope(scope_type="websocket"),
    ],
)
async def test_non_limited_scopes_bypass_body_buffering(scope: Scope) -> None:
    """Delegate safe, non-API, and non-HTTP scopes directly to the app."""

    downstream_called = False

    async def app(
        received_scope: Scope, receive: Receive, send: Send
    ) -> None:
        nonlocal downstream_called
        downstream_called = True
        assert received_scope is scope
        del receive, send

    middleware = RequestBodyLimitMiddleware(app, 4)
    assert await _run(middleware, scope, []) == []
    assert downstream_called is True
