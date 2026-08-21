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
    prime_http_metrics(
        route_methods={"/test/route": {"GET", "POST"}, "invalid": {"GET"}}
    )

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


def test_prime_http_metrics_empty_inputs_do_not_create_labels() -> None:
    """Empty inputs should be a no-op."""
    prime_http_metrics(route_methods={})

    value = REGISTRY.get_sample_value(
        "http_requests_total",
        {"method": "TRACE", "route": "/metrics/empty-input", "status": "200"},
    )
    assert value is None


def test_prime_http_metrics_primes_method_route_combinations() -> None:
    """Priming creates the Cartesian product of supplied methods and routes."""
    prime_http_metrics(
        route_methods={
            "/metrics/a": {"DELETE", "PATCH"},
            "/metrics/b": {"DELETE", "PATCH"},
        }
    )

    for method in ["DELETE", "PATCH"]:
        for route in ["/metrics/a", "/metrics/b"]:
            count = REGISTRY.get_sample_value(
                "http_requests_total",
                {"method": method, "route": route, "status": "200"},
            )
            assert count == 0.0

            histogram_count = REGISTRY.get_sample_value(
                "http_request_duration_seconds_count",
                {"method": method, "route": route},
            )
            assert histogram_count == 0.0

    unprimed = REGISTRY.get_sample_value(
        "http_requests_total",
        {"method": "POST", "route": "/metrics/a", "status": "200"},
    )
    assert unprimed is None


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
