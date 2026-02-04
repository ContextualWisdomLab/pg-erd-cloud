from __future__ import annotations

from starlette.responses import Response

from app.security_headers import apply_security_headers


def test_apply_security_headers_sets_defaults() -> None:
    response = Response("ok")
    apply_security_headers(response, is_https=False)

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Permissions-Policy"] == (
        "geolocation=(), microphone=(), camera=()"
    )
    assert "Strict-Transport-Security" not in response.headers


def test_apply_security_headers_sets_hsts_only_for_https() -> None:
    response = Response("ok")
    apply_security_headers(response, is_https=True)
    assert response.headers["Strict-Transport-Security"].startswith("max-age=")


def test_apply_security_headers_does_not_override_existing_values() -> None:
    response = Response("ok")
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Strict-Transport-Security"] = "max-age=0"

    apply_security_headers(response, is_https=True)

    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert response.headers["Strict-Transport-Security"] == "max-age=0"
