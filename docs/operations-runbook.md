# Operations Runbook

Status date: 2026-08-09
Scope: current standalone deployment; planned controls are labelled

This runbook records safe observation and escalation boundaries. It does not
pretend that missing automation exists, and it does not prescribe destructive
database repair without a reviewed incident plan.

## Deployment profiles

| Profile | Entry | Current fact |
| --- | --- | --- |
| Development | `docker compose up -d --build` | Vite, FastAPI and PostgreSQL on loopback; reload enabled |
| Production-style | `docker compose -f compose.prod.yaml up -d --build` | Traefik HTTP entry on 8080, static SPA, internal backend/PostgreSQL |
| External controls | TLS, WAF, shared rate limit, alert backend, secret registry | Deployment-owned and not provided by the committed stack |

The production-style stack is not an internet-production claim. Traefik is
published on host loopback only, so the supported reference path places the TLS
terminator on that host. Before exposure, inspect the direct peer Traefik sees
after Docker NAT, allowlist only its `/32` or `/128` CIDR in
`TRAEFIK_TRUSTED_PROXY_CIDRS`, and enforce approved egress/ingress outside the
stack. Because host-local callers traverse the same Docker gateway, this makes
the whole host—not only the TLS-terminator process—the forwarded-header trust
boundary. Use a dedicated terminator container/network identity or an
authenticated proxy protocol when hostile local processes are in scope.

## Start and health verification

1. Validate the exact image/source digest, Compose configuration, required
   secrets, database backup, and Alembic head.
2. Start the stack with the pinned Traefik image; treat an unknown-option/startup
   error as a failed deployment gate. Backend startup runs `alembic upgrade head`
   before serving.
3. Verify `/healthz` through the same edge path clients use.
4. Send requests from two known client addresses through the TLS terminator and
   verify backend structured logs report those client addresses—not one shared
   bridge/terminator address. Stop exposure if this proxy-hop preflight fails.
5. Verify an authenticated read, project-scoped snapshot read, and static
   `/share/<invalid-uuid>` SPA fallback without creating production data.
6. Check logs for migration, pooler detection, worker startup, secret/DSN
   disclosure, retry loops, and unexpected outbound targets.

`/healthz` is a process/service check, not proof that every target connector,
worker recovery path, OIDC provider, LLM provider, or external TLS control is
healthy.

## Observability

- Structured request logs and request correlation IDs are current.
- Prometheus metrics are opt-in and token protected. The committed Traefik
  config does not route `/metrics`; scrape it from an approved internal path or
  add a separately reviewed protected route.
- Track API latency/errors, 401/403/404/410/429 rates, queue depth/oldest age,
  `running` age, attempts/failures, worker heartbeat once implemented, target
  timeouts, public-share volume, and LLM cost/egress.
- Shared dashboards, alert thresholds, pager ownership and retention are
  `planned` deployment artifacts.

## Backup, restore and migrations

- Back up application PostgreSQL before migrations and verify restore into a
  disposable environment. A backup without a successful restore drill is not
  release evidence.
- Preserve Alembic history; reconcile ORM/physical drift with a new forward
  migration, never by modifying an applied revision.
- Test upgrade from every supported previous release and application rollback
  against the upgraded schema. Destructive/contract migrations require an
  expand/backfill/dual-read/contract sequence.
- Target databases are customer assets. pg-erd-cloud metadata backup does not
  replace target backup/PITR and the current deprecated apply endpoint has no
  production recovery guarantee.

## Secret and credential incidents

### Bearer share URL disclosed

Treat disclosure as an incident: the project owner should call
`DELETE /api/projects/{project_uuid}/share-links/{share_uuid}` immediately,
preserve access/log evidence, notify affected parties, and issue a replacement
only after risk review. New links expire according to `SHARE_LINK_TTL_HOURS`.
The current UI does not expose the revoke action; rotation and access-audit
automation remain `planned`. Public link validation is primary-consistent; an
immediately readable deleted UUID is therefore an incident and failed release
gate, not expected replica lag.

### `APP_SECRET` compromise or rotation

The key protects stored DSNs and current code has no automated rewrap workflow.
Do not rotate blindly: that can make existing connections unreadable. Inventory
affected connections, deploy a dual-key/rewrap migration, validate recovery,
rotate target credentials as needed, and remove the old key after evidence.
Migration from runtime environment settings to a credential registry is
`planned`.

### Target DSN or LLM/OIDC credential disclosure

Revoke/rotate at the authority, restrict network access, search redacted logs
and external providers, preserve incident evidence, and verify new credentials
through the approved bootstrap path. Never paste secret values into issues or
PR logs.

## Queue incident

Queued work persists and concurrent claim is exclusive, but a process crash can
strand queue and snapshot rows in `running` indefinitely. Alert on excessive
running age. Preserve job/snapshot/request IDs and worker logs; do not manually
flip state or replay a payload against production without idempotency and
handler-specific review. Lease/reclaim/retry/dead-letter automation is
`planned` under REL-010.

## Target connectivity/SSRF incident

Capture opaque connection/project/request IDs, resolved destination class,
connector/version and sanitized error. Never log the DSN. Disable the affected
connection or egress route, verify DNS and allowlist policy, and reproduce only
against a controlled target. Target allowlisting is fail-closed in code: an
empty allowlist rejects the connection. PostgreSQL connects to the validated IP
set, while Snowflake currently reconnects by account hostname; keep centralized
egress controls in place for that remaining DNS-rebinding gap.

## Dependency or CI security finding

Treat Medium and above as real until disproven. Record advisory, package/path,
severity, affected artifact and exact head; update the narrow dependency and
lock, rerun package audit plus required exact-head gates, and never weaken a
fail-closed workflow to make it green. Provider failure and vulnerability
remediation are separate facts.

## Escalation and evidence

Every incident record contains start/detection times, exact release SHA,
tenant-safe opaque IDs, impact, control decisions, commands/queries approved by
an operator, before/after evidence, customer communication, and follow-up
owner/due date. On-call roster, RTO/RPO, retention schedule and regional data
policy remain organization/deployment inputs and must be completed before an
SLA is offered.
