from __future__ import annotations

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.csrf import CSRF_HEADER_NAME, make_csrf_middleware


def make_request(
    method: str, path: str, headers: dict[str, str] | None = None
) -> Request:
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
async def test_csrf_allows_state_changing_api_with_token() -> None:
    middleware = make_csrf_middleware()

    response = await middleware(
        make_request("POST", "/api/projects", {CSRF_HEADER_NAME: "x" * 16}),
        ok_response,
    )

    assert response.status_code == 204
