"""Dependency contract for Starlette's supported synchronous test transport."""

import importlib
import sys
import warnings
from typing import Any

from starlette.applications import Starlette
from starlette.exceptions import StarletteDeprecationWarning
from starlette.responses import JSONResponse
from starlette.routing import Route


async def _healthz(request: object) -> JSONResponse:
    """Return a minimal response so the transport performs a real request."""

    return JSONResponse({"ok": True})


def _import_testclient_with_deprecations_as_errors() -> Any:
    """Re-run Starlette's transport selection instead of relying on import order."""

    module_name = "starlette.testclient"
    previous_module = sys.modules.pop(module_name, None)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", StarletteDeprecationWarning)
            return importlib.import_module(module_name).TestClient
    finally:
        sys.modules.pop(module_name, None)
        if previous_module is not None:
            sys.modules[module_name] = previous_module


def test_testclient_does_not_use_deprecated_httpx_transport() -> None:
    """Fail when Starlette falls back to its deprecated plain-httpx import path."""

    test_client = _import_testclient_with_deprecations_as_errors()
    app = Starlette(routes=[Route("/healthz", _healthz)])

    with test_client(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
