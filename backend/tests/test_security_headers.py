from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from app import security_headers
from app.security_headers import make_security_headers_middleware


def test_security_headers_present_on_healthz_and_api() -> None:
    """Baseline headers should be present on API + health endpoints."""
    app = FastAPI()
    app.middleware("http")(make_security_headers_middleware())

    @app.get("/healthz")
    def healthz() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app, base_url="https://testserver")
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "no-referrer"
    assert "Permissions-Policy" in r.headers
    assert "Content-Security-Policy" in r.headers
    assert (
        r.headers["Strict-Transport-Security"]
        == "max-age=31536000; includeSubDomains"
    )

    r2 = client.get("/api/ping")
    assert r2.status_code == 200
    assert "Content-Security-Policy" in r2.headers
    assert (
        r2.headers["Strict-Transport-Security"]
        == "max-age=31536000; includeSubDomains"
    )


def test_csp_not_applied_to_fastapi_docs_endpoints() -> None:
    """Swagger UI should not be broken by an overly strict CSP."""
    app = FastAPI()  # includes /docs by default
    app.middleware("http")(make_security_headers_middleware())
    client = TestClient(app, base_url="https://testserver")

    r = client.get("/docs")
    assert r.status_code == 200
    assert "Content-Security-Policy" not in r.headers

    # Non-canonical paths should also be treated as docs paths for CSP purposes.
    r2 = client.get("/DOCS")
    assert "Content-Security-Policy" not in r2.headers


def test_csp_path_normalization_handles_double_slash() -> None:
    """CSP checks should treat //docs as a docs path (no CSP)."""

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "//docs",
        "raw_path": b"//docs",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "root_path": "",
    }
    request = Request(scope)
    assert security_headers._should_apply_csp(request) is False
