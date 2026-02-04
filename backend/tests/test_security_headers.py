from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.security_headers import make_security_headers_middleware


def test_security_headers_present_on_healthz_and_api() -> None:
    app = FastAPI()
    app.middleware("http")(make_security_headers_middleware())

    @app.get("/healthz")
    def healthz() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["Referrer-Policy"] == "no-referrer"
    assert "Permissions-Policy" in r.headers

    r2 = client.get("/api/ping")
    assert r2.status_code == 200
    assert "Content-Security-Policy" in r2.headers


def test_csp_not_applied_to_fastapi_docs_endpoints() -> None:
    app = FastAPI()  # includes /docs by default
    app.middleware("http")(make_security_headers_middleware())
    client = TestClient(app)

    r = client.get("/docs")
    assert r.status_code == 200
    assert "Content-Security-Policy" not in r.headers
