from __future__ import annotations

from unittest.mock import patch
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY

from app.metrics import (
    normalize_route_label,
    prime_http_metrics,
    render_metrics,
)


def test_normalize_route_label_empty() -> None:
    """Empty routes normalize to 'unmatched'."""
    assert normalize_route_label("") == "unmatched"


def test_normalize_route_label_unmatched() -> None:
    """Explicitly 'unmatched' stays 'unmatched'."""
    assert normalize_route_label("unmatched") == "unmatched"


def test_normalize_route_label_no_leading_slash() -> None:
    """Routes lacking a leading slash map to 'unmatched'."""
    assert normalize_route_label("api/x/{id}") == "unmatched"
    assert normalize_route_label("foo") == "unmatched"


def test_normalize_route_label_valid() -> None:
    """Valid routes pass through."""
    assert normalize_route_label("/api/x/{id}") == "/api/x/{id}"
    assert normalize_route_label("/") == "/"


def test_prime_http_metrics() -> None:
    """Metrics should be primed in the registry to expose expected series."""
    # Run the prime function with dummy data.
    prime_http_metrics(methods={"GET", "POST"}, routes={"/test/route", "invalid"})

    # Check counters.
    # '/test/route' -> '/test/route'
    get_count = REGISTRY.get_sample_value(
        "http_requests_total",
        {"method": "GET", "route": "/test/route", "status": "200"},
    )
    assert get_count == 0.0

    post_count = REGISTRY.get_sample_value(
        "http_requests_total",
        {"method": "POST", "route": "/test/route", "status": "200"},
    )
    assert post_count == 0.0

    # 'invalid' -> 'unmatched'
    unmatched_count = REGISTRY.get_sample_value(
        "http_requests_total",
        {"method": "GET", "route": "unmatched", "status": "200"},
    )
    assert unmatched_count == 0.0

    # Check histograms
    get_hist_count = REGISTRY.get_sample_value(
        "http_request_duration_seconds_count",
        {"method": "GET", "route": "/test/route"},
    )
    assert get_hist_count == 0.0

    get_hist_sum = REGISTRY.get_sample_value(
        "http_request_duration_seconds_sum",
        {"method": "GET", "route": "/test/route"},
    )
    assert get_hist_sum == 0.0


def test_render_metrics() -> None:
    """Render metrics should return exposition format using a mocked generator."""
    with patch("app.metrics.generate_latest") as mock_generate:
        mock_generate.return_value = b"mocked_metric_total 42\n"

        data, content_type = render_metrics()

        assert content_type == CONTENT_TYPE_LATEST
        assert isinstance(data, bytes)
        assert data == b"mocked_metric_total 42\n"
        mock_generate.assert_called_once()


def test_normalize_route_label_none() -> None:
    """None routes normalize to 'unmatched'."""
    assert normalize_route_label(None) == "unmatched"


def test_normalize_route_label_whitespace() -> None:
    """Whitespace-only routes normalize to 'unmatched'."""
    assert normalize_route_label("   ") == "unmatched"
