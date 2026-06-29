from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from app.csrf import (
    CSRF_HEADER_NAME,
    generate_csrf_token,
    make_csrf_middleware,
    verify_csrf_token,
)
from app.main import app


def make_request(method: str, path: str, headers: dict[str, str] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "headers": [
                (name.lower().encode("latin1"), value.encode("latin1"))
                for name, value in (headers or {}).items()
            ],
        }
    )


async def ok_response(_: Request) -> Response:
    return Response(status_code=204)


@pytest.mark.asyncio
async def test_csrf_allows_safe_api_methods_without_token() -> None:
    middleware = make_csrf_middleware()

    response = await middleware(make_request("GET", "/api/projects"), ok_response)

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_csrf_rejects_state_changing_api_without_token() -> None:
    middleware = make_csrf_middleware()

    response = await middleware(make_request("POST", "/api/projects"), ok_response)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_csrf_rejects_unsigned_state_changing_api_token() -> None:
    middleware = make_csrf_middleware(token_secret="test-secret")

    response = await middleware(
        make_request("POST", "/api/projects", {CSRF_HEADER_NAME: "x" * 64}),
        ok_response,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_csrf_allows_state_changing_api_with_signed_token() -> None:
    middleware = make_csrf_middleware(token_secret="test-secret")
    token = generate_csrf_token("test-secret")

    response = await middleware(
        make_request("POST", "/api/projects", {CSRF_HEADER_NAME: token}),
        ok_response,
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_csrf_rejects_expired_token() -> None:
    middleware = make_csrf_middleware(token_secret="test-secret", ttl_seconds=10)
    token = generate_csrf_token("test-secret", now=100)

    response = await middleware(
        make_request("POST", "/api/projects", {CSRF_HEADER_NAME: token}),
        ok_response,
    )

    assert response.status_code == 403


def test_csrf_verifier_rejects_future_or_malformed_tokens() -> None:
    future_token = generate_csrf_token("test-secret", now=200)

    assert verify_csrf_token(future_token, "test-secret", now=100) is False
    assert verify_csrf_token("issued.nonce.signature", "test-secret") is False
    assert verify_csrf_token("100.nonce.!!", "test-secret", now=100) is False


def test_csrf_token_endpoint_returns_signed_token() -> None:
    client = TestClient(app)

    response = client.get("/api/csrf-token")

    assert response.status_code == 200
    token = response.json()["csrf_token"]
    assert verify_csrf_token(token, "test-secret")
