from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_cors_preflight_allows_configured_api_methods() -> None:
    """The production CORS middleware must allow every configured API method."""
    client = TestClient(app)

    for method in ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
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
