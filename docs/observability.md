# Observability Baseline

This document defines the **minimum observability baseline** for `pg-erd-cloud`:

- Central **structured logs** (JSON)
- Basic **metrics** (Prometheus exposition)
- Deployable **alert thresholds**

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

### /metrics exposure policy

- `/metrics` is **disabled by default** (`OBSERVABILITY_METRICS_ENABLED=false`).
- When enabled, it should only be reachable on **internal networks** or behind a
  reverse proxy with auth/IP allowlist.
- If you enable it directly on the app, set `OBSERVABILITY_METRICS_TOKEN` and
  send `X-Metrics-Token: <token>` from the Prometheus scraper.

### HTTP metrics

- `http_requests_total{method,route,status}`
- `http_request_duration_seconds_bucket|sum|count{method,route}`
- `authz_failures_total{status,route,reason}`
- `share_audit_events_total{action,outcome}`
- `billing_events_total{provider,event_type,outcome}`
- `llm_draft_requests_total{surface,artifact,outcome}`
- `llm_draft_input_chars_bucket|sum|count{surface,artifact}`
- `llm_draft_output_chars_bucket|sum|count{surface,artifact,outcome}`
- `product_events_total{area,action,outcome}`

### LLM usage logs

Live LLM draft paths also emit `event=llm_draft_usage` structured logs. These
logs include `surface`, `artifact`, `outcome`, UUID references, and input/output
character counts. They intentionally do not include prompt contents, snapshot
JSON, provider responses, or API keys.

The same live draft events are persisted to `llm_draft_usage_event` for monthly
billing attribution. Authenticated users can query
`GET /api/billing/llm-usage?month=YYYY-MM` to retrieve account-level request,
success, failure, quota-exceeded, input-character, and output-character totals.
Use those totals to reconcile provider invoices; do not log or store prompt
contents for this workflow.

`outcome=quota_exceeded` means the in-process LLM draft quota rejected the
request before any provider call. Authenticated routes use the account UUID as
the quota key; shared routes use the share-link UUID. `Retry-After` is returned
to the caller with the 429 response.

Shared live LLM draft exports also emit `event=share_audit` with
`outcome=success` or `outcome=denied`, so support can correlate a public export
or quota denial with the share link, project, snapshot, and request ID without
seeing prompt contents.

### Job queue metrics (DB-backed queue)

- `job_queue_jobs_total{job_type,outcome}`
  - `outcome`: `succeeded` | `failed`
- `job_queue_wait_seconds_bucket|sum|count{job_type}`
  - computed as `started_at - run_after`
- `job_queue_processing_seconds_bucket|sum|count{job_type,outcome}`
  - handler runtime

## 3) Alerting baseline

The deployable Prometheus rule file is:

- `deploy/prometheus/pg-erd-cloud-alerts.yml`

Tune thresholds per environment; the checked-in defaults are the commercial
readiness baseline. The operational interpretation, owner, escalation rule, and
release approval checklist are fixed in
`docs/operations/alert-thresholds.md`.

### API

- 5xx error spike
  - `PgErdCloudHigh5xxRate`: alert when `5xx / total` > 1% for 5 minutes
- Latency regression
  - `PgErdCloudHighRouteLatency`: alert when p95 latency > 1s for 10 minutes
    (per route group)
- 인증/인가 실패 급증
  - `PgErdCloudAuthzFailureSpike`: alert when
    `sum by (route,reason) (rate(authz_failures_total[5m]))` > 10/s
- 공유 감사 실패/비정상
  - `PgErdCloudShareAbuseOrFailureSpike`: alert when
    `sum by (action,outcome) (rate(share_audit_events_total{outcome=~"denied|failed"}[5m]))`
    > 5/s
- LLM draft 실패
  - `PgErdCloudLlmDraftFailures`: alert when live LLM draft configuration,
    prompt-size, or provider failures occur in the last 10 minutes.
- 결제 webhook/catalog 실패
  - `PgErdCloudBillingWebhookFailures`: alert when billing webhook auth,
    configuration, or configured plan catalog validation fails.

### Job queue

- Failure spike
  - `PgErdCloudJobFailures`: alert when
    `increase(job_queue_jobs_total{outcome="failed"}[10m])` > 0
- Backlog / wait time
  - `PgErdCloudJobQueueWaitHigh`: alert when p95 `job_queue_wait_seconds` >
    60s for 10 minutes

## 4) Validation (local)

Example:

```bash
# Request
curl -fsS -D- http://127.0.0.1:8000/healthz -o /dev/null

# Metrics
METRICS_TOKEN="<metrics-token>"  # required when /metrics is enabled
curl -fsS -H "X-Metrics-Token: $METRICS_TOKEN" \
  http://127.0.0.1:8000/metrics | head -50
```
