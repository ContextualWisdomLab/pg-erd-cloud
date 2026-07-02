"""Prometheus metrics for pg-erd-cloud.

This module intentionally keeps instrumentation lightweight and dependency
minimal. Metrics are exposed via /metrics (when enabled).
"""

from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)


def normalize_route_label(route: str) -> str:
    """Normalize a route label to avoid high-cardinality metrics.

    This codebase intentionally records *route templates* (e.g. `/api/x/{id}`)
    rather than raw request paths.
    """
    if not route:
        return "unmatched"
    if route == "unmatched":
        return route
    if not route.startswith("/"):
        return "unmatched"
    return route


def prime_http_metrics(*, route_methods: dict[str, set[str]]) -> None:
    """Create common label series so metrics show up before first traffic."""
    for route, methods in sorted(route_methods.items()):
        normalized = normalize_route_label(route)
        for method in sorted(methods):
            # Counters need an explicit sample.
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                route=normalized,
                status="200",
            ).inc(0)
            # Histograms can be created without observing.
            HTTP_REQUEST_DURATION_SECONDS.labels(method=method, route=normalized)


HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP responses by method/route/status.",
    ["method", "route", "status"],
)


HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds by method/route.",
    ["method", "route"],
)


AUTHZ_FAILURES_TOTAL = Counter(
    "authz_failures_total",
    "Total authorization/authentication failures by status, route, and reason.",
    ["status", "route", "reason"],
)


SHARE_AUDIT_EVENTS_TOTAL = Counter(
    "share_audit_events_total",
    "Total share audit events emitted by action and outcome.",
    ["action", "outcome"],
)


BILLING_EVENTS_TOTAL = Counter(
    "billing_events_total",
    "Total billing reconciliation webhook events by provider, type, and outcome.",
    ["provider", "event_type", "outcome"],
)


LLM_DRAFT_REQUESTS_TOTAL = Counter(
    "llm_draft_requests_total",
    "Total live LLM draft requests by surface, artifact, and outcome.",
    ["surface", "artifact", "outcome"],
)


LLM_DRAFT_INPUT_CHARS = Histogram(
    "llm_draft_input_chars",
    "Approximate input snapshot JSON size for live LLM drafts.",
    ["surface", "artifact"],
)


LLM_DRAFT_OUTPUT_CHARS = Histogram(
    "llm_draft_output_chars",
    "Output draft size for live LLM drafts by surface, artifact, and outcome.",
    ["surface", "artifact", "outcome"],
)


def record_llm_draft_metrics(
    *,
    surface: str,
    artifact: str,
    outcome: str,
    input_chars: int,
    output_chars: int | None = None,
) -> None:
    """Record low-cardinality LLM draft usage metrics."""
    LLM_DRAFT_REQUESTS_TOTAL.labels(
        surface=surface,
        artifact=artifact,
        outcome=outcome,
    ).inc()
    LLM_DRAFT_INPUT_CHARS.labels(surface=surface, artifact=artifact).observe(
        max(input_chars, 0)
    )
    if output_chars is not None:
        LLM_DRAFT_OUTPUT_CHARS.labels(
            surface=surface,
            artifact=artifact,
            outcome=outcome,
        ).observe(max(output_chars, 0))


PRODUCT_EVENTS_TOTAL = Counter(
    "product_events_total",
    "Total product lifecycle events by area, action, and outcome.",
    ["area", "action", "outcome"],
)


def record_product_event(area: str, action: str, outcome: str) -> None:
    """Record a low-cardinality product lifecycle event."""
    PRODUCT_EVENTS_TOTAL.labels(area=area, action=action, outcome=outcome).inc()


JOB_QUEUE_JOBS_TOTAL = Counter(
    "job_queue_jobs_total",
    "Total number of job queue executions by type/outcome.",
    ["job_type", "outcome"],
)


JOB_QUEUE_WAIT_SECONDS = Histogram(
    "job_queue_wait_seconds",
    "Time spent waiting in queue (started_at - run_after) in seconds.",
    ["job_type"],
)


JOB_QUEUE_PROCESSING_SECONDS = Histogram(
    "job_queue_processing_seconds",
    "Time spent processing a job (handler runtime) in seconds.",
    ["job_type", "outcome"],
)


def render_metrics() -> tuple[bytes, str]:
    """Render all metrics in Prometheus exposition format."""
    return generate_latest(), CONTENT_TYPE_LATEST
