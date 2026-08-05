from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


API_CORS_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")


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
