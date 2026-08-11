# ADR-0002: Isolated dry run and live read-only preflight

- **Decision status:** Accepted
- **Implementation status:** Partially implemented
- **Date:** 2026-08-09
- **Owners:** pg-erd-cloud maintainers and operators
- **Supersedes:** none
- **Related:** [ADR-0001](ADR-0001-server-authoritative-planning.md),
  [ADR-0003](ADR-0003-plan-execution-segmentation.md),
  [forward-engineering v1 contract](../contracts/forward-engineering-v1.md)

## Context

Running DDL inside `BEGIN` and then rolling it back does not make production a
safe dry-run environment. PostgreSQL can still acquire strong locks, scan or
rewrite tables, block application traffic, and consume material resources.
Rollback also cannot provide a universal contract for non-transactional
operations. Conversely, sandbox execution alone cannot prove that the live
target still matches the reviewed base or that its current data satisfies
operation-specific preconditions.

The current legacy `apply-sql` endpoint has a rollback-only mode. That mode is
useful for compatibility validation but is explicitly not the dry-run contract
for the model-to-plan workflow.

## Decision

One successful dry run consists of two independent evidence classes bound to
the same immutable plan digest and base digest.

1. **Disposable execution.** A `forward_dry_run` worker provisions or leases an
   isolated PostgreSQL database compatible with the target major version,
   materializes the complete operation-relevant dependency closure, executes
   the exact stored plan, re-introspects it, and requires the target digest.
   The sandbox is destroyed or sanitized after bounded evidence is persisted.
2. **Live read-only preflight.** A separately authorized worker re-introspects
   the live target, requires its canonical digest to equal the plan base digest,
   and runs bounded operation-specific read queries. Examples include proving
   table emptiness before adding a required column without a default, detecting
   NULL values before `SET NOT NULL`, and probing type convertibility. Timeouts
   and incomplete evidence are non-success states.

The isolation boundary is mandatory:

- the sandbox receives no production target credentials and has no network
  route to production targets;
- the live-preflight worker has only the guarded target route and cannot turn a
  preflight operation into DDL;
- the application metadata database is never used as the migration sandbox;
- target connections continue to use the existing encrypted-secret,
  TLS-verification, DNS-resolution, SSRF-validation, and IP-pinning boundary;
- neither worker persists row values, DSNs, or credential-bearing diagnostics.

Live preflight is evidence, not a concurrency guarantee. Apply must repeat the
schema fingerprint and data-aware preconditions after acquiring the declared
locks on the execution connection.

## Consequences

### Positive

- Production receives no DDL during dry run.
- Exact SQL executability and semantic convergence are tested, not inferred.
- Review distinguishes sandbox evidence from facts observed on the live target.
- Drift prevents execution before any live DDL.

### Costs and risks

- Deployment needs a version-compatible sandbox service, lifecycle cleanup,
  egress isolation, capacity controls, and separate credentials.
- Dependency closure must be lossless for every admitted operation. Unknown
  views, triggers, checks, defaults, partitions, domains, extensions, operator
  classes, RLS policies, grants, or similar dependencies block dry run.
- Live read queries need bounded timeouts and must not expose row content.
- A passed dry run can become stale; the apply path must revalidate.

## Alternatives rejected

- **DDL plus rollback on the live target.** Rejected because rollback does not
  undo lock, scan, rewrite, or resource impact.
- **Sandbox execution without live preflight.** Rejected because it cannot prove
  current live fingerprint or data preconditions.
- **Live preflight without executable sandbox validation.** Rejected because
  static analysis does not prove the exact plan executes and converges.
- **Reuse the metadata database.** Rejected because target DDL would share a
  failure and privilege boundary with pg-erd-cloud control-plane data.

## Repository evidence

### Implemented

- Plans contain base/target digests and structured statement preconditions.
- `app.forward.isolated_dry_run` verifies the persisted plan digest, compiler
  version, PostgreSQL major, strict materialized-base digest, supported
  all-transactional operation list, and bounded timeouts before executing the
  exact compiler-owned statements in one sandbox transaction. It masks driver
  failures, rolls back after a started transaction, preserves cancellation,
  re-introspects through a worker-owned callback, and requires the strict
  target digest. The PostgreSQL 14–18 matrix exercises the real DDL/catalog
  round trip. This is an execution core, not evidence that a deployed sandbox
  is disposable or isolated.
- Existing target-connection code provides encrypted DSNs and guarded database
  connection primitives that the planned live-preflight worker must reuse.
- `app.forward.live_preflight` compiles only the structured
  `table_is_empty`, `no_null_values`, and `castable_values` preconditions into
  server-owned quoted reads. It enforces a 1,000-query ceiling, PostgreSQL type
  validation, one read-only repeatable-read transaction, bounded server/client
  timeouts, boolean-only evidence, and fixed non-secret database failures.
  It also adapts a caller-supplied snapshot through the strict capability
  boundary and returns only its canonical digest plus exact plan-base match.
  This is a primitive, not a worker or completed live-preflight claim.

### Planned before production release

- isolated sandbox provisioning, complete base dependency materialization,
  cleanup, and egress enforcement;
- application worker wiring with a separately constrained read-only target
  identity and guarded connection lifecycle;
- worker-owned fresh target capture and binding to the same authorized
  connection/attempt before invoking the implemented digest comparison;
- durable, redacted evidence and a frontend presentation of both evidence
  classes.

## Acceptance evidence

An integration test must observe the exact plan executing in the sandbox,
verify that the live target received only bounded reads, prove sandbox cleanup
on success and failure, and show that a live fingerprint mismatch produces a
terminal drift result before any DDL.
