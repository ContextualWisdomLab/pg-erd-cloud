from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from app import security_headers
from app.csrf import CSRF_HEADER_NAME
from app.main import CORS_ALLOW_HEADERS
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
        r.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"
    )

    r2 = client.get("/api/ping")
    assert r2.status_code == 200
    assert r2.headers["X-Content-Type-Options"] == "nosniff"
    assert r2.headers["X-Frame-Options"] == "DENY"
    assert r2.headers["Referrer-Policy"] == "no-referrer"
    assert "Permissions-Policy" in r2.headers
    assert "Content-Security-Policy" in r2.headers
    assert (
        r2.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains"
    )


def test_hsts_not_set_on_http_even_if_x_forwarded_proto_is_https() -> None:
    """Regression: do not trust X-Forwarded-Proto for HSTS."""
    app = FastAPI()
    app.middleware("http")(make_security_headers_middleware())

    @app.get("/api/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app, base_url="http://testserver")
    r = client.get("/api/ping", headers={"X-Forwarded-Proto": "https"})
    assert r.status_code == 200
    assert "Strict-Transport-Security" not in r.headers


def test_security_headers_present_on_cors_preflight() -> None:
    """Security headers should be present on CORS preflight responses."""
    app = FastAPI()

    @app.get("/api/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Register headers middleware after CORS so it runs outermost.
    app.middleware("http")(make_security_headers_middleware())

    client = TestClient(app)
    r = client.options(
        "/api/ping",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code in (200, 204)
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "no-referrer"
    assert "Permissions-Policy" in r.headers
    assert "Strict-Transport-Security" not in r.headers


def test_cors_preflight_allows_csrf_token_header() -> None:
    """Cross-origin state-changing requests must be allowed to send CSRF token."""
    app = FastAPI()

    @app.post("/api/projects")
    def create_project() -> dict[str, bool]:
        return {"ok": True}

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://example.com"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=CORS_ALLOW_HEADERS,
    )

    client = TestClient(app)
    r = client.options(
        "/api/projects",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": f"{CSRF_HEADER_NAME}, Content-Type",
        },
    )

    assert r.status_code in (200, 204)
    assert CSRF_HEADER_NAME.lower() in r.headers["Access-Control-Allow-Headers"].lower()


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


def test_apply_security_headers_directly() -> None:
    """apply_security_headers should set baseline headers on direct call."""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/ping",
        "raw_path": b"/api/ping",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "root_path": "",
    }
    request = Request(scope)
    response = Response()

    security_headers.apply_security_headers(request, response)

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "Permissions-Policy" in response.headers
    assert "Content-Security-Policy" in response.headers
    assert "Strict-Transport-Security" not in response.headers


def test_apply_security_headers_https_hsts() -> None:
    """apply_security_headers should apply HSTS when scheme is HTTPS."""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/api/ping",
        "raw_path": b"/api/ping",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "root_path": "",
    }
    request = Request(scope)
    response = Response()

    security_headers.apply_security_headers(request, response)

    assert "Strict-Transport-Security" in response.headers


def test_apply_security_headers_does_not_overwrite() -> None:
    """apply_security_headers should not overwrite existing headers."""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/api/ping",
        "raw_path": b"/api/ping",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "root_path": "",
    }
    request = Request(scope)
    response = Response()

    # Pre-set some headers
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Strict-Transport-Security"] = "max-age=0"

    security_headers.apply_security_headers(request, response)

    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert response.headers["Strict-Transport-Security"] == "max-age=0"
