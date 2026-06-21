from __future__ import annotations

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


def test_prime_http_metrics_empty() -> None:
    """Priming with empty methods or routes should not crash and not add unwanted metrics."""
    # Clear labels that might have been set by other tests
    try:
        from app.metrics import HTTP_REQUESTS_TOTAL, HTTP_REQUEST_DURATION_SECONDS

        HTTP_REQUESTS_TOTAL.clear()
        HTTP_REQUEST_DURATION_SECONDS.clear()
    except AttributeError:
        pass

    prime_http_metrics(methods=set(), routes=set())

    # Ensure nothing was primed unexpectedly
    val = REGISTRY.get_sample_value(
        "http_requests_total",
        {"method": "GET", "route": "unmatched", "status": "200"},
    )
    assert val is None


def test_prime_http_metrics_combinations() -> None:
    """Priming should correctly handle multiple methods and routes (Cartesian product)."""
    prime_http_metrics(methods={"GET", "DELETE"}, routes={"/a", "/b"})

    # Check all combinations are primed
    for method in ["GET", "DELETE"]:
        for route in ["/a", "/b"]:
            count = REGISTRY.get_sample_value(
                "http_requests_total",
                {"method": method, "route": route, "status": "200"},
            )
            assert count == 0.0

            hist_count = REGISTRY.get_sample_value(
                "http_request_duration_seconds_count",
                {"method": method, "route": route},
            )
            assert hist_count == 0.0

    # Ensure un-primed combinations remain None
    unprimed = REGISTRY.get_sample_value(
        "http_requests_total",
        {"method": "POST", "route": "/a", "status": "200"},
    )
    assert unprimed is None


def test_render_metrics() -> None:
    """Render metrics should return exposition format."""
    # Ensure some metric is primed.
    prime_http_metrics(methods={"DELETE"}, routes={"/test/render"})

    data, content_type = render_metrics()

    assert content_type == CONTENT_TYPE_LATEST
    assert isinstance(data, bytes)

    # Check that our primed metric appears in the rendered output
    assert b'method="DELETE"' in data
    assert b'route="/test/render"' in data
    assert b"http_requests_total" in data
