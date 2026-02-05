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
