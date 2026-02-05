# Observability (MVP)

This document defines the **minimum observability baseline** for `pg-erd-cloud`:

- Central **structured logs** (JSON)
- Basic **metrics** (Prometheus exposition)
- Suggested **alert thresholds**

Scope is intentionally small (issue #49) and can be expanded once the runtime
stack (Kubernetes/VM, managed monitoring, etc.) is finalized.

## 1) Structured logs (JSON)

The backend emits one JSON log event per request.

### Event: `http_request`

Fields:

- `ts` (string, RFC3339-ish): UTC timestamp
- `event` (string): fixed to `http_request`
- `request_id` (string, UUID): request correlation id
- `method` (string): HTTP method
- `route` (string): route template when available (e.g. `/api/projects/{id}`)
- `status` (number): HTTP status code
- `duration_ms` (number): request duration in milliseconds
- `client_ip` (string): client IP (uses `X-Forwarded-For` only when
  `API_RATE_LIMIT_TRUST_X_FORWARDED_FOR=true`)

Notes:

- We intentionally **do not** log request/response bodies.
- Keep log ingestion/retention policies aligned with security requirements.

## 2) Metrics (Prometheus)

When enabled, the backend exposes metrics at:

- `GET /metrics` (not included in OpenAPI schema)

### HTTP metrics

- `http_requests_total{method,route,status}`
- `http_request_duration_seconds_bucket|sum|count{method,route}`

### Job queue metrics (DB-backed queue)

- `job_queue_jobs_total{job_type,outcome}`
  - `outcome`: `succeeded` | `failed`
- `job_queue_wait_seconds_bucket|sum|count{job_type}`
  - computed as `started_at - run_after`
- `job_queue_processing_seconds_bucket|sum|count{job_type,outcome}`
  - handler runtime

## 3) Alerting (suggested baseline)

Tune thresholds per environment; these are reasonable starting points.

### API

- 5xx error spike
  - alert when `5xx / total` > 1% for 5 minutes
- Latency regression
  - alert when p95 latency > 1s for 10 minutes (per route group)

### Job queue

- Failure spike
  - alert when `job_queue_jobs_total{outcome="failed"}` increases above baseline
    or failure rate > 5% for 10 minutes
- Backlog / wait time
  - alert when p95 `job_queue_wait_seconds` > 60s for 10 minutes

## 4) Validation (local)

Example:

```bash
# Request
curl -fsS -D- http://127.0.0.1:8000/healthz -o /dev/null

# Metrics
curl -fsS http://127.0.0.1:8000/metrics | head -50
```
