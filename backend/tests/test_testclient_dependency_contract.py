"""Dependency contract for Starlette's supported synchronous test transport."""

import warnings

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient


async def _healthz(request: object) -> JSONResponse:
    """Return a minimal response so the transport performs a real request."""

    return JSONResponse({"ok": True})


def test_testclient_does_not_use_deprecated_httpx_transport() -> None:
    """Fail when Starlette falls back to its deprecated plain-httpx TestClient path."""

    app = Starlette(routes=[Route("/healthz", _healthz)])

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "error",
            message=(
                r"Using httpx with starlette\.testclient is deprecated; "
                r"install httpx2 instead\."
            ),
        )
        with TestClient(app) as client:
            response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
