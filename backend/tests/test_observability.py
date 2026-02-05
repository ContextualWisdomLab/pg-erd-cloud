from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.observability import setup_observability
from app.settings import settings


def test_request_id_header_and_metrics_endpoint() -> None:
    """Observability middleware should attach request id and expose /metrics."""
    prev_metrics = settings.observability_metrics_enabled
    prev_logging = settings.observability_request_logging_enabled
    settings.observability_metrics_enabled = True
    settings.observability_request_logging_enabled = True
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

        m = client.get("/metrics")
        assert m.status_code == 200
        assert "http_requests_total" in m.text
        assert "job_queue_jobs_total" in m.text
    finally:
        settings.observability_metrics_enabled = prev_metrics
        settings.observability_request_logging_enabled = prev_logging
