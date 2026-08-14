# Forward Engineering Operational Runbook

- **Runbook status:** Accepted operating design; not yet executable end to end
- **Runtime status:** Partially implemented; structured production apply is Planned
- **Applies to:** PostgreSQL 14–18 forward-engineering v1
- **Last reconciled with the working tree:** 2026-08-11

> Do not use this runbook as evidence that structured production apply exists.
> The repository persists model revisions, migration plans, durable run/event
> evidence, integrity-checked polling, an editor-authorized cancellation API,
> and a deployer-confirmed apply intent that creates no dispatch. Isolated dry
> run and live-preflight execution cores are Partial; deployed worker binding,
> apply execution, reconciliation, verification, alerts, and the application
> kill switch remain **Planned** release gates.

The legacy `POST /api/connections/{uuid}/apply-sql` endpoint is a transitional
compatibility path. Its rollback mode operates on the live target and therefore
does not satisfy the dry-run procedure below. Persistent use requires deployer
role but lacks plan, approval, drift, event, and convergence binding.

## Status and authority

| Capability | Availability | Operational conclusion |
|---|---|---|
| Canonical model save/revision with `If-Match` | Implemented | May be used as a control-plane preview feature. |
| Structured immutable plan compilation/persistence | Implemented bounded subset | May be reviewed; blocked plans are not executable. |
| Real-target preflight and plan expiry enforcement | Partial | Structured bounded boolean reads, `execute_bound_live_preflight` same-transaction snapshot/check binding, the query-only `capture_postgres_snapshot` callback for a caller-owned connection/transaction, `complete_live_preflight` server-derived terminal CAS, `complete_isolated_dry_run` sandbox result binding, DB-durable hashed attempt ownership, execution-neutral consumer-to-attempt binding, and provider-neutral sandbox/preflight orchestration with cooperative cancellation deadlines exist. The guarded stored-target lookup releases only exact project-owned encrypted DSN ciphertext/nonce under the live run/plan/attempt predicate and never decrypts or opens the target. Snapshot capture rejects a missing caller transaction before catalog reads or optional Citus savepoint access. PostgreSQL 14–18 CI uses a restricted ephemeral target login, reuses that same authorized connection for snapshot capture, and proves DDL denial. In-process cancellation cannot forcibly terminate a non-cooperative provider. Deployed process isolation/kill, decryption, target-connection/provider composition, credential/route constraints, application startup wiring, worker operation, and target audit evidence are absent, so no plan is production-authorized. |
| Isolated disposable PostgreSQL dry run | Partially implemented | Exact signed-plan execution, rollback, version/base checks, target-digest convergence, and `complete_isolated_dry_run` server-derived success CAS have a PostgreSQL 14–18-tested core. Provisioning, dependency materialization, deployed isolation/egress proof, cleanup, and worker binding are Planned; no current result is release evidence. |
| Durable dry-run/apply states and events | Partially implemented | Storage, CAS/event integrity, polling, cancellation intent and terminal acknowledgement, terminal redelivery without sandbox/preflight replay, an execution-neutral consumer contract, consumer-to-attempt binding, and an exact deployer-confirmed apply intent with no dispatch exist; no application startup wiring, sandbox lifecycle, apply executor, or recovery worker exists. |
| Stored-plan executor and in-lock revalidation | Partial foundation | The execution-neutral compiler deterministically sorts/deduplicates existing-table lock targets from structured statement references and fails closed for missing/unknown compiler versions and unknown/non-transactional/tampered operations. It parses no rendered SQL and acquires no target lock. Dispatch, target connection/credential binding, lock acquisition, in-lock drift/precondition revalidation, DDL, commit, recovery, and verification remain Planned; do not enable structured live apply. |
| Post-apply re-introspection and convergence | Planned | No current API may claim verified convergence. |
| Browser forward-engineering workflow | Partially implemented | Read-only plan review, bounded dry-run intent, exact passed-evidence/typed-target non-dispatched apply intent, verified run polling/audit, and exact-version cancellation are available. The apply intent control is **Partially implemented** and does not dispatch or execute. Apply execution/recovery and composed browser E2E remain Planned; do not simulate success. |

The PostgreSQL 14–18 CI matrix composes each metadata server with a
digest-pinned ephemeral Valkey 8 service. It verifies that a sanitized handler
failure abandons the exact durable attempt and releases the exact signal, then
that retry completes the next attempt before acknowledgement and removes all
ready/processing/token entries. It then leaves one one-second signal/attempt
pair unacknowledged, waits for actual expiry, and proves a successor reclaims
both stores, marks the expired attempt abandoned, reaches `passed`, completes
the successor, and rejects the stale signal. This is in-process ephemeral
recovery evidence only; it does not prove process/container restart or authorize
deployment startup wiring, credentials, or worker execution.

Actors:

- **Editor:** save/revise models, compile plans, request dry run when available.
- **Deployer:** authorize live apply after every evidence gate passes.
- **Operator:** monitor durable states, contain incidents, collect evidence, and
  coordinate database recovery. Operator access does not imply deployer intent.
- **Database owner:** validate target privileges, backup/recovery posture, and
  manual remediation when a destructive outcome cannot be automatically
  reversed.

## Production enablement checklist

Every item is **Planned** until an implementation link and immutable CI or
operational artifact is attached to the release record.

- [ ] Dedicated sandbox service matches each admitted target PostgreSQL major,
  cannot route to production, and never receives production credentials.
- [ ] Live preflight credential is read-only; execution credential has only the
  object-specific DDL authority required by the plan.
- [ ] Application metadata database is not used as a sandbox.
- [ ] Target allowlist, DNS/IP pinning, TLS policy, certificate roots, firewall
  egress, and credential rotation are tested in the deployment environment.
- [x] Run/event/outbox migrations, idempotency uniqueness, compare-and-swap
  transitions, atomic identifier-only dispatch creation, cancellation intent
  and terminal acknowledgement, terminal no-replay settlement, and evidence
  redaction are verified by repository tests.
- [x] Due dispatch claiming uses `FOR UPDATE SKIP LOCKED` and exact-attempt
  publish-state CAS in a caller-owned transaction.
- [x] One bounded publisher emits only `migration_run_uuid` on a dedicated
  Valkey key before exact-attempt acknowledgement; it neither commits nor
  executes work.
- [x] A digest-pinned real Valkey 8 CI service verifies dedicated-key UUID-only
  membership and generic-pop isolation through the production adapter.
- [x] An opt-in scheduled relay lifecycle uses one transaction per UUID-only
  claim, bounded polling, fixed non-secret failure logging, startup validation,
  and cooperative application shutdown. Set `JOB_QUEUE_BACKEND=valkey`, a
  usable `VALKEY_URL` or Sentinel configuration,
  `MIGRATION_DISPATCH_RELAY_ENABLED=true`, and a positive
  `MIGRATION_DISPATCH_RELAY_POLL_INTERVAL_SECONDS` to enable it. This does not
  start a queue consumer, load a plan, or execute SQL.
- [x] Atomic ready-to-processing claim, bounded expiry reclaim, exact lease
  renewal, acknowledgement, and retry release use an exact lease-token. A stale
  claimant cannot extend or complete a successor lease, an expired signal
  owner cannot renew, renewal cannot shorten the current expiry, and the ready
  payload remains only
  `migration_run_uuid`.
- [x] The execution-neutral consumer contract is **Implemented**. It calls one
  injected handler with the exact signal claim (run UUID plus opaque
  lease-token), acknowledges only after success, releases only the exact lease
  at a bounded retry time after sanitized failure, and fails closed on lost
  lease ownership. The ready payload remains UUID-only. It does not load plans,
  credentials, SQL, or target data. Application startup wiring and worker
  execution remain **Planned**.
- [x] Automatic heartbeat is **Implemented** in the execution-neutral consumer.
  It renews only the exact claim while the injected handler runs, cancels and
  retrieves the handler task on renewal loss, and never acknowledges that loss
  as success. No consumer startup wiring or execution worker is implied.
- [x] DB-durable attempt ownership primitives are **Implemented**. They store
  only hashed worker/signal-token identity, permit one active owner, reclaim
  only expiry, and require exact unexpired-owner CAS for renew/finish.
  Consumer-to-attempt binding is **Implemented** as an execution-neutral
  dual-lease adapter that commits acquire/renew/finish in fresh transactions
  and cancels injected work on durable ownership loss. Application startup
  wiring, credentials, and worker execution remain **Planned**.
- [ ] Relay deployment restart/failover, application startup wiring, worker execution,
  recovery, retry exhaustion, and retention are verified in the deployment
  environment.
- [ ] `lock_timeout`, `statement_timeout`, and transaction timeout policy have
  finite environment-specific values below the incident-response objective.
  No repository default currently establishes forward-worker values.
- [ ] One active apply per target/plan authority is enforced, and deterministic
  advisory/object lock ordering is tested with external writers.
- [ ] Backup, restore, point-in-time recovery, and destructive-change owner are
  confirmed before plans capable of data loss can be approved.
- [ ] Feature-specific metrics and alerts distinguish queue delay, dry-run
  failure, drift, rollback, verification failure, applied-with-drift, and
  `outcome_unknown` without high-cardinality or secret labels.
- [ ] Application apply kill switch and a separately tested ingress/database
  containment procedure are available.
- [x] Legacy persistent `apply-sql` is disabled by default for the product
  workflow; retirement remains a separate release decision.

## Normal planned procedure

### 1. Freeze and review the plan

1. Confirm the plan references the intended project, connection name, succeeded
   base snapshot, model revision, compiler version, and unexpired timestamp.
2. Compare the model revision digest, base digest, target digest, and plan
   digest with the UI/API response. Never use “latest” as an executable
   identifier.
3. Review every executable statement and review-only proposed statement,
   dependency, required privilege, precondition, lock mode, possible
   scan/rewrite, data-loss flag, blocker, and risk count. The risk summary
   includes proposals even when execution is blocked.
   Treat structured `object_ref`/`dependency_refs` as authoritative; joined
   labels are display-only and can collide for delimiter-bearing identifiers.
4. Stop if any blocker exists or `can_dry_run=false`. The compiler must return
   `statements=[]` when blocked. `proposed_statements` may retain independently
   supported deltas for review, but they are never executable in that plan.
5. Treat primary-key changes, comments/order changes, unsupported constraints,
   indexes, defaults, identity/generated columns, partitions, views, triggers,
   policies, grants, extensions, DML/backfills, and non-transactional work
   according to the current support matrix. Unsupported means stop, not omit.
6. Confirm safe type aliases were canonicalized to PostgreSQL catalog spelling;
   serial pseudo-types are unsupported, and every admitted type alteration is
   conservatively destructive with possible rewrite, scan, and data loss.
7. Reject and recapture any snapshot without the current capability-contract
   version. Dropped column slots are unsupported in this slice.

### 2. Run isolated validation

1. Submit the exact plan UUID and digest with a new idempotency key.
2. Confirm the queued run is persisted before external I/O and the queue
   payload contains only `migration_run_uuid`.
3. Require sandbox major-version compatibility and complete dependency closure.
4. Execute the stored structured plan in the sandbox, then re-introspect it.
5. Require the sandbox digest to equal `target_digest`. Destroy or sanitize the
   sandbox after bounded evidence is persisted.
6. Run live **read-only** fingerprint and data-aware preconditions. Do not run
   live DDL. Incomplete, timed-out, or redaction-failed evidence is failure.
7. The terminal CAS must persist the lowercase canonical observed digest on the
   run and chained event. It accepts `passed` only for exact plan-base equality
   and `drifted` only for inequality after plan-integrity revalidation.
8. Proceed only from `passed`; `drifted`, `failed`, and `cancelled` are terminal
   non-success results.

### 3. Authorize live apply

This section's intent-creation boundary is implemented. Completing it produces
only a durable queued intent and chained confirmation evidence; it creates no
outbox dispatch, queue signal, credential access, target connection, SQL, or
DDL execution. Every operation in section 4 remains Planned.

1. Confirm the actor has server-verified deployer authority.
2. Bind the exact unexpired plan/digest, current model revision, and passed
   dry-run UUID for the same base observation.
   The server locks the schema-model row `FOR UPDATE`; `stale_revision` means a
   successor model revision won and no intent was created.
3. Require the deployer to type the exact connection name.
4. Require a separate destructive acknowledgement when any operation has
   destructive severity or data-loss risk.
5. Submit once using a new idempotency key. Identical reuse returns the original
   run; different input under the same key returns `409`.
6. Verify the returned intent has no dispatch. Stop here until the separately
   reviewed executor, apply-time revalidation, and recovery gates are enabled.

The current execution-neutral revalidation manifest may be compiled for review
from the exact stored plan digest. It binds PostgreSQL compatibility and
base/target digests to deterministic object-lock targets, structured database
`CREATE`/schema `CREATE`/table `OWNER` requirements, and structured data checks.
It rejects compiler-v1 privilege-label drift and a check whose table is not
covered by its statement lock.
For a non-empty v1 plan it also describes exactly one ordered all-transactional
segment; a no-op plan has no segment. It does not acquire a target connection,
observe a target role's privileges, start that transaction, prove rollback, or
make step 2 below true.

The privilege-probe compiler re-derives the manifest from the exact signed plan
and expected digest, then maps only those exact structured requirements to fixed
read queries. Schema/table names are parameters, not rendered SQL. The
compiled probes are reviewable inputs; compiling them does not execute a query,
identify the target role, or prove that a result came from the locked execution
connection.

The pure observation assessor may validate that caller-supplied digest,
privilege, and precondition rows are complete and positionally identical to the
manifest. Its base-match and aggregate booleans are untrusted input assessment,
not proof of freshness, target identity, held locks, same-connection capture,
or permission to continue to DDL.

The bounded capture primitive may run those exact observations on a
caller-owned connection. It re-derives the signed manifest, starts one
read-only repeatable-read transaction, captures the strict snapshot, executes
the fixed privilege probes and structured preconditions in order, commits only
the read transaction, and returns the pure assessment. A fixed failure means no
assessment. This does not bind the connection to the stored target or durable
attempt, acquire advisory/object locks, or permit DDL. Do not reuse its result
as apply authority; apply must repeat revalidation after locks are held.

### 4. Execute and verify

1. Worker reloads the run, plan, revision, target, and evidence from metadata;
   it does not trust queue or browser copies.
2. Acquire the target advisory lock, begin the transaction, acquire object
   locks in deterministic qualified-name order, and recheck base fingerprint
   and data preconditions on that same connection.
3. If any recheck fails, execute no plan DDL and record `drifted_no_apply` or a
   classified non-success state.
4. Set bounded PostgreSQL lock, statement, and transaction timeouts; execute
   the single all-transactional segment. A statement/postcondition failure must
   roll back the whole segment and produce `failed_rolled_back` only when the
   rollback is proven.
5. After known commit, re-introspect using the same connection and schema
   filter, persist a dedicated verification snapshot, and compare its canonical
   digest to `target_digest`.
6. Report `verified` only for exact digest equality. A known commit plus
   residual diff is `applied_with_drift`; unavailable verification is
   `verification_failed`.

## Fail-closed decision table

| Observation | Required action | Permitted automatic retry? | Terminal/outcome claim |
|---|---|---:|---|
| Plan has blockers, unknown kind/version, oversized payload, or expired timestamp | Reject before queueing. | No; create a reviewed successor plan. | No DDL |
| Model revision or plan digest changed | Return stale/conflict; require review of the successor. | No | No DDL |
| Target fingerprint differs before dry run or apply | Stop and re-introspect; invalidate old evidence. | No | `drifted` or `drifted_no_apply`; no DDL |
| Sandbox cannot materialize dependencies or does not converge | Destroy/sanitize sandbox; retain bounded error evidence. | Only a stage proven isolated and idempotent | `failed`; no live DDL |
| Live preflight is incomplete or times out | Stop. Do not interpret absence of evidence as success. | New dry-run attempt after cause is resolved | `failed`; no live DDL |
| Role, target confirmation, destructive acknowledgement, or passed dry run is missing | Reject authorization. | No automatic retry | No DDL |
| Lock acquisition or in-lock precondition times out | Roll back and release resources. | New reviewed apply attempt only if DDL is proven not started | Non-success; no DDL if pre-execution proof exists |
| Statement fails and transaction rollback is proven | Persist failure and rollback evidence. | Never automatically replay apply | `failed_rolled_back` |
| Commit succeeds but verification fails | Preserve known-commit evidence; resume verification only. | Verification may retry; DDL may not | `verification_failed` |
| Commit succeeds and residual diff is observed | Stop and escalate for DBA/product review. | No DDL replay | `applied_with_drift` |
| Commit acknowledgement is lost | Re-introspect before any conclusion. | Reconciliation/evidence collection only | Target digest → `verified`; base digest → `not_applied`; otherwise `outcome_unknown` |
| `outcome_unknown` | Freeze the run, alert, preserve evidence, and require manual target investigation. | **No automatic or operator one-click DDL replay** | No applied/not-applied claim |

## Timeout handling

The target worker must set finite, separately observable values for:

- connection timeout before a transaction;
- PostgreSQL `lock_timeout` for advisory and object locks;
- `statement_timeout` for preconditions and each plan statement;
- transaction timeout policy for the complete execution boundary;
- sandbox provisioning/execution/cleanup; and
- verification/reconciliation.

**Status: Planned.** Numeric defaults and configuration names are not present
for a forward worker. They must be defined, tested against representative table
sizes, and documented per deployment before enablement. A timeout is a
classified failure, never evidence that a transaction rolled back or did not
commit. Do not report `failed_rolled_back` without rollback evidence.

## Kill switch and containment

### Planned application kill switch

The structured workflow must add a deny-by-default server-side apply gate
checked both when an apply run is queued and immediately before `applying`.
The exact configuration contract is **Planned** and must be frozen in the TRD
and deployment manifests. Disabling it must:

- reject new apply-run requests while preserving read/model/plan operations;
- prevent queued runs from entering `applying`;
- leave already applying runs in reconciliation/verification rather than
  killing them and falsely claiming rollback; and
- emit a bounded audit event and operator metric.

### Current emergency containment

`LEGACY_PERSISTENT_APPLY_ENABLED=false` is the built-in default and rejects new
persistent compatibility requests before credential access. If an operator had
explicitly enabled the route, restore the setting to `false` and restart/roll
the backend, then coordinate these external controls for in-flight or uncertain
work:

1. Block `POST /api/connections/*/apply-sql` at the ingress/API policy layer if
   rollout of the disabled setting is not yet complete.
2. Revoke the target database role's DDL privileges or rotate/disable the
   affected connection credential.
3. Preserve metadata and application logs; do not delete plan/revision records.
4. Check target `pg_stat_activity`, locks, server logs, and schema state with the
   database owner before restoring access.

Blocking a route or stopping a process does not prove that an in-flight
transaction rolled back. Determine the database outcome independently.

## Recovery by terminal state

| State | Operator procedure |
|---|---|
| `cancelled` | Confirm the worker never entered `applying`; retain the event trail. |
| `drifted` / `drifted_no_apply` | Capture a new succeeded snapshot, explain drift, create/revise the desired model, and compile a new plan. Never reuse old evidence. |
| `failed_rolled_back` | Verify rollback/connection evidence, fix the cause, then start from a newly reviewed plan or new dry run. Never auto-requeue. |
| `not_applied` | Reconciliation proved the exact base digest. A new apply still requires fresh evidence and explicit deployer intent. |
| `verification_failed` | Retry only read-only verification. Do not run DDL; commit is known. |
| `applied_with_drift` | Preserve residual diff and known-commit evidence; stop related automation; involve the target owner. Remediation is a new reviewed plan or a DBA-managed recovery, never generated rollback. |
| `outcome_unknown` | Disable further applies to the target, preserve evidence, inspect catalogs/server logs/backups with the DBA, and document the conclusion. The system and operator UI must offer no replay action. |
| `verified` | Confirm the persisted verification snapshot UUID and target digest, review event completeness, and close the change record. |

Automatic rollback generation is **Rejected**. Transaction rollback handles
only a known failure before commit in the v1 segment. Destructive changes after
a known or possible commit require a new explicitly reviewed forward plan or
the database owner's tested backup/point-in-time recovery process.

## Evidence bundle

Retain bounded, redacted evidence sufficient to answer what was authorized,
observed, executed, and verified:

- project, connection, model revision, plan, dry-run, apply-run, and actor UUIDs;
- compiler version; revision, base, target, plan, request, and confirmation
  digests;
- plan statement/risk/blocker counts and operation kinds, not a copied SQL
  batch in queue/event/log payloads;
- timestamps and durations for state changes, locks, statements,
  reconciliation, and verification;
- precondition/postcondition result categories without row values;
- commit/rollback acknowledgement classification;
- verification snapshot UUID, observed digest, and bounded residual diff; and
- correlation/request identifiers and sanitized diagnostic code.

Never retain decrypted DSNs, passwords/tokens, raw credential-bearing driver
errors, arbitrary client SQL, complete row samples, or secrets in metric labels.

## Escalation and closure

Escalate immediately for destructive unexpected change, sustained target
blocking, credential exposure, cross-project access, missing audit events,
`applied_with_drift`, `verification_failed` beyond the verification objective,
or any `outcome_unknown`.

Closure requires:

1. target database owner confirmation;
2. preserved and redacted evidence bundle;
3. documented root cause and whether DDL committed;
4. new tests or controls for the failure mode;
5. threat model, ADR/contract, and this runbook updated if the operating model
   changed; and
6. a newly reviewed plan for any remediation, never reuse of the incident run.

## Related authority

- [Architecture](../../ARCHITECTURE.md)
- [Forward-engineering v1 contract](../contracts/forward-engineering-v1.md)
- [UML and state machines](../UML.md)
- [Data model](../DATA_MODEL.md)
- [Threat model](../security/forward-engineering-threat-model.md)
- [Test strategy](../TEST_STRATEGY.md)
- [ADR-0004: durable runs and recovery](../adr/ADR-0004-durable-runs-and-recovery.md)
