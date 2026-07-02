from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
import re
from starlette.requests import Request

from app.license_gate import require_active_license
from app.observability import _get_client_ip, _get_route_template, setup_observability
from app.settings import settings


def test_request_id_header_and_metrics_endpoint() -> None:
    """Observability middleware should attach request id and expose /metrics."""
    prev_metrics = settings.observability_metrics_enabled
    prev_logging = settings.observability_request_logging_enabled
    prev_token = settings.observability_metrics_token
    settings.observability_metrics_enabled = True
    settings.observability_request_logging_enabled = True
    settings.observability_metrics_token = "test-token"
    try:
        app = FastAPI()

        @app.get("/healthz")
        def healthz() -> dict[str, bool]:
            return {"ok": True}

        setup_observability(app)
        client = TestClient(app)

        r = client.get("/healthz")
        assert r.status_code == 200
        assert "X-Request-Id" in r.headers

        unauth = client.get("/metrics")
        assert unauth.status_code == 403

        wrong = client.get("/metrics", headers={"X-Metrics-Token": "wrong-token"})
        assert wrong.status_code == 403

        m = client.get("/metrics", headers={"X-Metrics-Token": "test-token"})
        assert m.status_code == 200
        assert "http_requests_total" in m.text
        assert "job_queue_jobs_total" in m.text
    finally:
        settings.observability_metrics_enabled = prev_metrics
        settings.observability_request_logging_enabled = prev_logging
        settings.observability_metrics_token = prev_token


def test_get_route_template_with_route() -> None:
    class MockRoute:
        path = "/api/v1/users/{user_id}"

    req = Request({"type": "http", "headers": [], "route": MockRoute()})
    assert _get_route_template(req) == "/api/v1/users/{user_id}"


def test_get_route_template_without_route() -> None:
    req = Request({"type": "http", "headers": []})
    assert _get_route_template(req) == "unmatched"


def test_get_route_template_empty_path() -> None:
    class MockRoute:
        path = ""

    req = Request({"type": "http", "headers": [], "route": MockRoute()})
    assert _get_route_template(req) == "unmatched"


def test_http_exception_authz_logs(caplog: pytest.LogCaptureFixture) -> None:
    app = FastAPI()
    setup_observability(app)

    @app.get("/api/private")
    def private() -> None:
        raise HTTPException(status_code=401, detail="missing bearer token")

    with caplog.at_level("WARNING"):
        with TestClient(app) as client:
            response = client.get("/api/private")

    assert response.status_code == 401
    assert response.json() == {"detail": "missing bearer token"}
    assert any(
        "authz_failure" in record.message and "status\":401" in record.message
        for record in caplog.records
    )
    assert any(
        "\"detail\":\"missing bearer token\"" in record.message
        for record in caplog.records
    )


@pytest.mark.parametrize(
    ("trust_xff", "headers", "client", "expected_ip"),
    [
        # trust_xff=False, client missing
        (False, [], None, "unknown"),
        # trust_xff=False, client present
        (False, [], ("192.168.1.1", 12345), "192.168.1.1"),
        # trust_xff=False, client missing host (None)
        (False, [], (None, 12345), "unknown"),
        # trust_xff=False, client host empty string
        (False, [], ("", 12345), "unknown"),
        # trust_xff=False, X-Forwarded-For is ignored
        (
            False,
            [(b"x-forwarded-for", b"10.0.0.1")],
            ("192.168.1.1", 12345),
            "192.168.1.1",
        ),
        # trust_xff=True, single IP
        (True, [(b"x-forwarded-for", b"10.0.0.1")], ("192.168.1.1", 12345), "10.0.0.1"),
        # trust_xff=True, multiple IPs (takes the right-most one, nearest trusted proxy)
        (
            True,
            [(b"x-forwarded-for", b"10.0.0.1, 10.0.0.2")],
            ("192.168.1.1", 12345),
            "10.0.0.2",
        ),
        # trust_xff=True, empty XFF value falls back to client
        (True, [(b"x-forwarded-for", b"")], ("192.168.1.1", 12345), "192.168.1.1"),
        # trust_xff=True, whitespace XFF value falls back to client
        (True, [(b"x-forwarded-for", b" , ")], ("192.168.1.1", 12345), "192.168.1.1"),
        # trust_xff=True, XFF not present falls back to client
        (True, [], ("192.168.1.1", 12345), "192.168.1.1"),
        # trust_xff=True, XFF not present and client missing falls back to unknown
        (True, [], None, "unknown"),
    ],
)
def test_get_client_ip(
    trust_xff: bool,
    headers: list[tuple[bytes, bytes]],
    client: tuple[str | None, int] | None,
    expected_ip: str,
) -> None:
    """_get_client_ip should extract IP correctly based on headers and trust settings."""
    # Temporarily set the setting for the test
    prev_trust = settings.api_rate_limit_trust_x_forwarded_for
    settings.api_rate_limit_trust_x_forwarded_for = trust_xff
    try:
        scope: dict[str, object] = {
            "type": "http",
            "headers": headers,
        }
        if client is not None:
            scope["client"] = client

        req = Request(scope)
        assert _get_client_ip(req) == expected_ip
    finally:
        settings.api_rate_limit_trust_x_forwarded_for = prev_trust


def test_authz_failure_metrics_are_recorded() -> None:
    prev_metrics = settings.observability_metrics_enabled
    prev_logging = settings.observability_request_logging_enabled
    prev_token = settings.observability_metrics_token
    settings.observability_metrics_enabled = True
    settings.observability_request_logging_enabled = True
    settings.observability_metrics_token = "test-token"
    try:
        app = FastAPI()

        @app.get("/api/private")
        def private() -> None:
            raise HTTPException(status_code=401, detail="missing bearer token")

        setup_observability(app)
        with TestClient(app) as client:
            _ = client.get("/api/private")

            metrics = client.get(
                "/metrics",
                headers={"X-Metrics-Token": "test-token"},
            ).text

        metric_lines = [
            line
            for line in metrics.splitlines()
            if line.startswith("authz_failures_total")
        ]
        assert metric_lines, "authz_failures_total metric should be present"
        assert any(
            'status="401"' in line
            and 'route="/api/private"' in line
            and 'reason="missing_bearer_token"' in line
            for line in metric_lines
        )
    finally:
        settings.observability_metrics_enabled = prev_metrics
        settings.observability_request_logging_enabled = prev_logging
        settings.observability_metrics_token = prev_token


def test_license_gate_sets_error_code_and_metrics() -> None:
    """License enforcement failures should emit error code headers and metrics."""
    prev_mode = settings.license_mode
    prev_key = settings.license_key
    prev_metrics = settings.observability_metrics_enabled
    prev_logging = settings.observability_request_logging_enabled
    prev_token = settings.observability_metrics_token
    settings.license_mode = "required"
    settings.license_key = "x" * 32
    settings.observability_metrics_enabled = True
    settings.observability_request_logging_enabled = True
    settings.observability_metrics_token = "test-token"

    try:
        app = FastAPI()

        @app.get("/api/private-license", dependencies=[Depends(require_active_license)])
        def private_license_route() -> dict[str, str]:
            return {"ok": "true"}

        setup_observability(app)
        client = TestClient(app)

        response = client.get("/api/private-license")
        assert response.status_code == 403
        assert response.headers["X-Error-Code"] == "license_key_invalid"
        assert response.headers.get("X-Request-Id")

        metrics = client.get(
            "/metrics",
            headers={"X-Metrics-Token": "test-token"},
        ).text

        assert any(
            line.startswith("authz_failures_total")
            and 'status="403"' in line
            and 'route="/api/private-license"' in line
            and 'reason="license_key_invalid"' in line
            for line in metrics.splitlines()
        )
    finally:
        settings.license_mode = prev_mode
        settings.license_key = prev_key
        settings.observability_metrics_enabled = prev_metrics
        settings.observability_request_logging_enabled = prev_logging
        settings.observability_metrics_token = prev_token
