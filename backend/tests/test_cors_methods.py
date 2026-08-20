from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


API_CORS_METHODS = ("GET", "POST", "PUT", "DELETE", "OPTIONS")
UNSUPPORTED_API_CORS_METHOD = "PATCH"


def test_cors_preflight_allows_every_supported_api_method() -> None:
    """Production CORS preflight must accept every HTTP method exposed by the API."""

    client = TestClient(app)

    for method in API_CORS_METHODS:
        response = client.options(
            "/api/projects",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

        assert response.status_code in (200, 204)
        allowed_methods = {
            item.strip()
            for item in response.headers["Access-Control-Allow-Methods"].split(",")
        }
        assert method in allowed_methods


def test_cors_preflight_rejects_unexposed_api_method() -> None:
    """Production CORS must reject methods that have no registered API route."""

    client = TestClient(app)
    response = client.options(
        "/api/projects",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": UNSUPPORTED_API_CORS_METHOD,
            "Access-Control-Request-Headers": "Content-Type",
        },
    )

    assert response.status_code == 400
    allowed_methods = {
        item.strip()
        for item in response.headers["Access-Control-Allow-Methods"].split(",")
    }
    assert UNSUPPORTED_API_CORS_METHOD not in allowed_methods
