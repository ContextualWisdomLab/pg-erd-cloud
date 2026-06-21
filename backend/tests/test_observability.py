from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.observability import setup_observability
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
    from app.observability import _get_route_template

    class MockRoute:
        path = "/api/v1/users/{user_id}"

    class MockRequest:
        def __init__(self):
            self.scope = {"route": MockRoute()}

    req = MockRequest()
    assert _get_route_template(req) == "/api/v1/users/{user_id}"  # type: ignore


def test_get_route_template_without_route() -> None:
    from app.observability import _get_route_template

    class MockRequest:
        def __init__(self):
            self.scope = {}

    req = MockRequest()
    assert _get_route_template(req) == "unmatched"  # type: ignore


def test_get_route_template_empty_path() -> None:
    from app.observability import _get_route_template

    class MockRoute:
        path = ""

    class MockRequest:
        def __init__(self):
            self.scope = {"route": MockRoute()}

    req = MockRequest()
    assert _get_route_template(req) == "unmatched"  # type: ignore
