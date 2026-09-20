"""Verify CORS reflects every cross-origin API mutation method."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.main import CORS_ALLOW_HEADERS, CORS_ALLOW_METHODS


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE"])
def test_cors_preflight_allows_implemented_api_methods(method: str) -> None:
    """The dev SPA must be able to preflight every method used by routers."""

    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=False,
        allow_methods=CORS_ALLOW_METHODS,
        allow_headers=CORS_ALLOW_HEADERS,
    )

    response = TestClient(app).options(
        "/api/resource",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": method,
        },
    )

    assert response.status_code in (200, 204)
    allowed = response.headers["Access-Control-Allow-Methods"].split(", ")
    assert method in allowed
