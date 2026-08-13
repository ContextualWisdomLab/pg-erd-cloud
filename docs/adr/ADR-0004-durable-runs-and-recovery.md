# ADR-0004: Durable runs, idempotency, cancellation, and recovery

- **Decision status:** Accepted
- **Implementation status:** Partially implemented; durable storage,
  identifier-only transactional outbox, lock-scoped claim/publish-state CAS,
  bounded scheduled UUID-only queue publication, exact lease-token
  ready/processing claim-ack-release primitives, execution-neutral consumer
  contract, DB-durable hashed attempt ownership and dual-lease binding, polling,
  and dry-run creation/cancellation intent APIs exist, while application startup
  wiring, workers, deployment failover, and recovery do not
- **Date:** 2026-08-09
- **Owners:** pg-erd-cloud maintainers and operators
- **Supersedes:** none
- **Related:** [ADR-0002](ADR-0002-isolated-dry-run-and-preflight.md),
  [ADR-0003](ADR-0003-plan-execution-segmentation.md),
  [ADR-0005](ADR-0005-authority-approvals-and-convergence.md),
  [forward-engineering v1 contract](../contracts/forward-engineering-v1.md)

## Context

Dry run, target preflight, lock waits, execution, reconciliation, and
re-introspection exceed a reliable HTTP request lifetime. A process may fail
before, during, or immediately after commit. Retrying an apply merely because a
queue lease expired can execute a destructive plan twice or misreport an
ambiguous outcome.

The repository has a generic `JobQueue`, but it does not model an immutable plan
attempt, evidence, approval, target observation, commit ambiguity, or
append-only state history.

## Decision

Dry run and apply are durable `migration_run` resources. The API persists the
run, genesis event, and identifier-only transactional outbox before external
I/O, then returns `202`. The `migration_run_dispatch` row contains only its
own identity, `migration_run_uuid`, dispatch kind, delivery state, bounded
attempt metadata, and timestamps; it never contains DSNs, raw SQL, plan JSON,
or row values. The implemented bounded publisher claims one due row with
`FOR UPDATE SKIP LOCKED`, publishes only `migration_run_uuid` on a dedicated
Valkey sorted-set key, and acknowledges that exact attempt in one caller-owned
transaction. It neither commits nor executes work. Publication failure raises
before acknowledgement so the caller rolls back the claim, while consumers
must tolerate at-least-once redelivery after an ambiguous publish.

The signal adapter atomically reclaims expired processing leases and moves one
due UUID-only ready member to an isolated processing set. A consumer-generated
exact lease-token is stored separately from the ready payload; only that token
may perform exact lease renewal, acknowledgement, or release. An expired signal
owner cannot renew; renewal is monotonic and cannot shorten the current expiry.
This prevents a stale claimant
from extending or acknowledging a successor lease. The execution-neutral
consumer invokes only an injected handler with the exact signal claim (run UUID
plus opaque lease-token), acknowledges after success, releases that exact lease
at a bounded retry time after a sanitized failure, and treats lost
acknowledgement or release ownership as non-success. The ready payload remains
UUID-only. Automatic heartbeat is **Implemented** around the injected handler:
renewal loss cancels and retrieves its task and cannot be acknowledged as
success. The consumer still does not load execution material, access a target,
or execute SQL, and is not wired into application startup.

`migration_run_attempt` ownership primitives are **Implemented** separately.
Acquisition locks the active dry run, permits one active attempt, marks only an
expired predecessor abandoned, and assigns a monotonic per-run attempt number.
Only SHA-256 hashes of a bounded worker identity and the opaque Valkey signal
lease token are persisted. Renewal requires the exact unexpired owner and an
uncancelled executable run and never shortens expiry; finish requires that same
unexpired owner. These primitives grant no credential or execution authority.
Consumer/startup integration, credential routing, and worker execution remain
Planned.

Each run binds:

- one immutable plan UUID and digest;
- run kind (`dry_run` or `apply`);
- actor and project;
- unique idempotency key scoped to the effective action;
- observed live base digest and bounded evidence;
- current state plus compare-and-swap version;
- redacted classified error, timestamps, and verification outcome.

Apply intent creation is **Implemented without execution authority**. The
deployer route verifies the immutable plan digest and expiry, exact target
connection name, same-plan `passed` dry run with exact observed base, and the
plan's destructive-confirmation requirement. Migration
`0012_apply_intent_confirmation` persists the restrictive passed-dry-run
self-reference, confirmation digest, and destructive boolean. Its genesis
event is hash chained, but no `migration_run_dispatch` row or Valkey signal is
created. Apply-time drift/privilege checks, locks, credentials, execution,
reconciliation, and verification remain Planned.

`migration_run_event` is append-only and records state transitions,
confirmation, drift, commit acknowledgement, reconciliation, and verification
using identifiers, hashes, counts, and sanitized diagnostics.
Each event carries a versioned canonical digest and its predecessor; the parent
run anchors the latest digest. Writers update the anchor and append the new link
in one caller-owned transaction. Readers recompute the chain. This detects
accidental or partial row mutation but is not a signature and cannot defeat an
attacker with authority to rewrite the complete metadata database.

Dry-run states are:

`queued -> sandbox_running -> live_preflight_running -> passed | drifted | failed`

Apply states are:

`queued -> applying -> reconciling -> verifying -> verified | drifted_no_apply | not_applied | verification_failed | failed_rolled_back | applied_with_drift | outcome_unknown`

Rules:

- compare-and-swap transitions and a uniqueness constraint select one winner
  for duplicate submissions;
- a dry-run may enter `passed` only when its canonical observed base digest
  equals the integrity-checked immutable plan base, and `drifted` only when it
  differs; the CAS stores the digest on the run and same-version chained event;
- cancellation may succeed only before a worker enters `applying`; after that
  point the system records a cancellation request but finishes reconciliation
  and verification rather than claiming execution stopped;
- dry-run jobs may retry only stages proven not to mutate the target;
- an apply is never automatically replayed after `applying` begins;
- a lost commit acknowledgement triggers re-introspection: exact target digest
  becomes `verified`, exact base digest becomes `not_applied`, and unavailable
  or third-state evidence becomes `outcome_unknown`;
- operators may resume evidence collection, but no recovery path may replay DDL
  from `outcome_unknown` automatically.

## Consequences

### Positive

- HTTP disconnects do not erase work or encourage duplicate applies.
- Terminal states distinguish “no DDL,” “rolled back,” “known committed,” and
  “unknown” outcomes.
- Auditors receive a durable sequence rather than mutable log text.
- The UI can poll one bounded resource and truthfully survive page closure.

### Costs and risks

- The control plane needs run/event tables, uniqueness constraints, queue
  outbox semantics, stale-lease handling, and retention policy.
- State transitions require careful compare-and-swap tests.
- `outcome_unknown` requires operator attention and must be prominent in UI and
  alerts.
- Event payload redaction and cardinality limits must be enforced centrally.

## Alternatives rejected

- **Execute within the HTTP request.** Rejected because disconnect and timeout
  behavior cannot provide durable state or safe recovery.
- **Use the generic queue row as the only record.** Rejected because queue
  delivery state is not migration outcome or audit evidence.
- **At-least-once automatic apply retry.** Rejected because commit may already
  have succeeded.
- **Collapse every failure to `failed`.** Rejected because operators need to
  know whether DDL ran and whether replay is forbidden.

## Repository evidence

### Implemented

- A generic `JobQueue` and snapshot job pattern exist for durable background
  work.
- Persisted migration plans provide the immutable input identity for future
  runs.
- `MigrationRun` and `MigrationRunEvent` ORM models plus Alembic revision 0010
  persist idempotent run identity and append-only ordered evidence.
- `MigrationRunDispatch` is the identifier-only transactional outbox. Its
  unique run foreign key prevents duplicate dispatch identities, database
  checks admit only isolated dry-run dispatch and consistent pending/published
  timestamps, and its due index supports bounded relay claiming.
- `claim_one_migration_dispatch` orders due work, uses
  `FOR UPDATE SKIP LOCKED`, and increments attempt state inside the caller's
  open transaction; `mark_migration_dispatch_published` accepts only that
  exact attempt and does not commit.
- `publish_one_migration_dispatch` publishes only the claimed run UUID to a
  dedicated Valkey key before exact-attempt acknowledgement. The caller owns
  commit/rollback; the function never loads the plan or executes SQL.
- `run_migration_dispatch_relay_forever` is an explicit opt-in application
  lifecycle. It owns one fresh transaction per claim, rolls failed iterations
  back through the transaction context, emits only a fixed non-secret failure
  code, polls at a positive configured interval, and is cancelled and awaited
  on shutdown. Startup rejects an unconfigured Valkey backend; client import,
  URL validity, and connectivity failures surface in relay iterations after
  startup.
- UUID-only signal claim, expiry reclaim, exact lease-token acknowledgement,
  and scheduled release are implemented and verified against real Valkey. The
  execution-neutral consumer contract is **Implemented**; application startup
  wiring and worker execution remain **Planned**.
- Database checks constrain run kind, current state, positive state version,
  positive event sequence, predecessor presence, and lowercase SHA-256 digest
  shapes; uniqueness selects one run per hashed
  project/run-kind idempotency identity, `request_digest` distinguishes
  conflicting reuse, and at most one event is allowed per run sequence. The
  polling boundary separately verifies that every sequence through the current
  state version exists and is contiguous.
- `app.forward.migration_run` owns the exact transition graph, bounded
  idempotency-key hashing, versioned request digests binding project, plan,
  run kind, plan digest, and actor, plus recursive rejection of SQL/credential
  fields and PostgreSQL connection-string values in evidence.
- `transition_migration_run` performs an optimistic update matching the exact
  UUID, kind, state, and state version, then appends the same-version sanitized
  event in the caller-owned transaction. A stale worker cannot publish evidence.
- `create_migration_run` uses the database idempotency constraint to select one
  exact dry-run or apply-intent winner. Dry-run creation appends sequence-one
  evidence plus one dispatch row. Apply-intent creation validates and persists
  exact confirmation bindings plus sequence-one evidence but creates no
  dispatch. Neither path commits, publishes, accesses credentials, or executes.
- Cancellation is a same-state, version-incrementing CAS event. A repeated
  request is idempotent, a terminal run rejects it, and a worker holding the old
  version must reload the intent before any further transition.
- Attempt-bound signal handling now acknowledges that persisted intent with a
  locked, exact-version transition to terminal `cancelled` before signal
  acknowledgement. Queued cancellation does not set `started_at`. A redelivered
  terminal run is acknowledged without acquiring another attempt or replaying
  sandbox/live-preflight work; either path locks and abandons a surviving active
  attempt before acknowledgement. This is metadata recovery, not deployed
  process interruption or apply authority.
- Event digest contract `migration-run-event/v1` covers run UUID, sequence,
  type, state, sanitized evidence, actor, normalized UTC time, and predecessor;
  the run CAS matches and advances `latest_event_digest`, and polling verifies
  every link plus the terminal anchor before exposing evidence.

### Planned before production release

- apply executor and apply-time drift/privilege/lock/precondition revalidation;
- application startup wiring, deployed in-flight process cancellation, and
  relay deployment restart/failover evidence;
- reconciliation and post-commit verification workers;
- operational metrics, alerts, retention, and recovery runbooks.

## Acceptance evidence

Concurrency tests must produce one accepted run for duplicate keys. Fault
injection before execution, before commit, after commit, and before verification
must produce the documented terminal state without automatic DDL replay.
