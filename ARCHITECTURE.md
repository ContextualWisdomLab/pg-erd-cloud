# pg-erd-cloud Architecture

## Status legend

- **Implemented**: present in production source and covered by repository tests.
- **Partial**: a safe bounded subset exists; unsupported behavior fails closed.
- **Planned**: approved design only; the product must not claim runtime support.

## Bounded contexts

```mermaid
flowchart TD
  UI[ERD editor and review UI] --> API[FastAPI control plane]
  API --> MODEL[(schema_model / schema_model_revision)]
  API --> COMPILER[Canonical model and plan compiler]
  COMPILER --> PLAN[(migration_plan)]
  PLAN -. partial core .-> SANDBOX[Isolated PostgreSQL validator]
  PLAN -. planned .-> PREFLIGHT[Read-only target preflight]
  PREFLIGHT -. planned .-> EXECUTOR[Durable migration executor]
  EXECUTOR -. planned .-> TARGET[(Target PostgreSQL)]
  TARGET --> INTROSPECTOR[PostgreSQL introspector]
  INTROSPECTOR --> SNAPSHOT[(schema_snapshot / schema_snapshot_data)]
```

Solid arrows are current control-plane or reverse-engineering paths. Dotted
arrows are accepted target architecture and do not claim deployed runtime
support.

## Component status

| Component | Responsibility | Status |
|---|---|---|
| React/Vite ERD editor | Snapshot visualization, editing, export | **Implemented existing product**; desired-model adapters and live workflow **Planned** |
| FastAPI control plane | Auth, tenancy, revisions, plan creation | **Partially implemented** |
| Canonical model/compiler | Validate, hash, compile operations/blockers | **Implemented for narrow v1 subset** |
| Metadata PostgreSQL | Snapshots, models, revisions, plans, jobs | Phase 1 entities, run/event/outbox storage, verified polling, dry-run creation/cancellation, lease-bound hashed worker-attempt primitives, and the exact dual-lease adapter **Implemented**; application worker wiring **Planned** |
| Isolated PostgreSQL validator | Exact-plan executable dry run | Signed-plan/version/base/transaction/convergence execution core and `complete_isolated_dry_run` server-derived success CAS **Partially implemented**; provisioning, dependency materialization, isolation proof, cleanup, and worker **Planned** |
| Live preflight/apply worker | Read-only evidence, locked execution, recovery | Bounded structured read-query, canonical snapshot/base-digest comparison, and DB-durable hashed attempt acquire/renew/finish primitives **Implemented**; `execute_bound_live_preflight` binds a caller-owned capture callback and checks to one read-only repeatable-read transaction, and `complete_live_preflight` derives the only valid terminal CAS classification. Consumer-to-attempt binding is **Implemented** as an execution-neutral dual-lease adapter; application startup wiring, credential binding, worker execution, and apply remain **Planned**. |
| External target PostgreSQL | Reverse source and future apply target | Reverse **Implemented**; target apply workflow **Planned** |

The browser is an intent and review surface, never a SQL authority. The API
persists immutable model revisions. The compiler validates a deliberately small
PostgreSQL 14–18 model, renders a structured transactional plan, associates
each statement with dependencies, privileges, preconditions and operational
risk, and binds the plan to an exact model revision, connection and succeeded
snapshot. Mixed-case, Unicode, reserved-word and quoted identifiers are
preserved and quoted server-side.

## Current implementation boundary

Implemented in the initial safe vertical slice:

- optimistic versioned model persistence using a strong revision-UUID `ETag`
  and `If-Match` token (the content digest remains separate);
- canonical model hashing independent of OIDs and capture timestamps;
- immutable server-side plans for schemas, tables, columns, nullability, types
  and creation-time primary keys;
- explicit risk, lock, rewrite/scan/data-loss, privilege and precondition data;
- one read-only repeatable-read catalog snapshot with an explicit capability
  contract version, plus a strict adapter/compiler that reject stale or lossy input;
- optimistic compare-and-swap run transitions that update one exact state
  version and append the matching sanitized evidence event in the caller's
  transaction; dry-run `passed`/`drifted` transitions revalidate immutable plan
  integrity, require the canonical observed base digest, enforce match/mismatch
  semantics, and persist that digest on both the run and chained event;
- an internal PostgreSQL conflict-winner writer that creates or reuses one
  exact, unexpired, executable dry-run intent and atomically persists its
  sequence-one event plus identifier-only dispatch outbox;
- an editor-authorized `POST /api/migration-plans/{plan_uuid}/dry-runs`
  boundary that requires the exact reviewed digest and bounded
  `Idempotency-Key`, then returns only the queued durable identity without
  publishing the outbox or signaling a worker;
- lock-scoped relay primitives that claim one due dispatch with
  `FOR UPDATE SKIP LOCKED`, increment its attempt in the caller-owned
  transaction, publish only `migration_run_uuid` to a dedicated Valkey sorted
  set, and publish-state CAS only that exact identifier-only claim;
- an explicit opt-in application lifecycle repeatedly invokes that bounded
  publisher in one fresh metadata transaction per claim, rolls failed
  publication back, idles at a positive configured interval, and shuts down
  cooperatively; it does not load plans, consume signals, or execute SQL;
- UUID-only ready signals can be atomically moved to an isolated processing
  set with a bounded exact lease-token, renewable only before expiry, reclaimed
  after expiry, acknowledged only by the current token, or released for a
  scheduled retry. These are
  execution-neutral consumer contract and consumer-safety primitives only: no
  application consumer lifecycle or migration worker exists;
- DB-durable `migration_run_attempt` history serializes acquisition on the run,
  stores only SHA-256 hashes of bounded worker identity and the opaque signal
  lease token, permits one active attempt per run, reclaims only expired owners,
  renews monotonically by exact CAS while the run remains executable, and
  finishes only an unexpired exact owner. Consumer-to-attempt binding is
  **Implemented** by an execution-neutral dual-lease adapter, but no application
  startup task, credential, sandbox, target, or DDL authority exists;
- same-state, version-incrementing cancellation intent that forces a worker to
  observe cancellation before its next CAS transition can win;
- an editor-authorized `POST /api/migration-runs/{run_uuid}/cancel` boundary
  that binds the exact state version, actor, and request correlation identity
  to that cancellation event and returns only stable sanitized error codes;
- a versioned SHA-256 event chain anchored on each run row; polling recomputes
  every link and fails closed on payload, ordering, predecessor, or anchor drift;
- a bounded live-preflight primitive compiles only the plan's structured
  `table_is_empty`, `no_null_values`, and `castable_values` preconditions into
  quoted PostgreSQL reads, executes them in one read-only repeatable-read
  transaction with server/client timeouts, and returns boolean-only evidence;
  `execute_bound_live_preflight` additionally runs a caller-owned fresh
  snapshot callback and those checks in the same read-only repeatable-read
  transaction, returning the canonical observed digest and plan-base match;
  `complete_live_preflight` accepts only that exact bounded result shape and
  derives `drifted`, `failed`, or `passed` plus bounded aggregate evidence for
  the existing durable CAS; neither function owns credentials, application
  worker wiring, or DDL authority;
- an execution-only isolated-dry-run primitive accepts no DSN or browser SQL,
  verifies the immutable plan/compiler/PostgreSQL-major/base bindings, executes
  only the compiler-owned all-transactional statement list with bounded
  timeouts, rolls failures back with fixed diagnostics, and requires a fresh
  strict snapshot to equal `target_digest`; PostgreSQL 14–18 CI supplies the
  real catalog round trip. `complete_isolated_dry_run` accepts only that exact
  success shape, revalidates it against the stored plan, and derives the fixed
  `live_preflight_running` CAS; sandbox provisioning, dependency
  materialization, network isolation, cleanup, and worker wiring remain absent;
- `viewer < editor < deployer < owner`, with persistent legacy SQL apply
  restricted to `deployer`.

Partial: the current compiler rejects foreign keys, indexes, defaults,
identity/generated columns, existing-primary-key changes, views, triggers,
partitions, extensions and distributed tables. This is a release blocker for
general forward engineering, not a silent omission.

Consumer-to-attempt binding is **Implemented** without execution authority.
Planned: isolated sandbox lifecycle, application startup wiring and worker execution,
live-preflight credential binding around the durable attempt and caller-owned
same-transaction snapshot primitive, plan approval, idempotent apply,
post-commit re-introspection and the
accessible frontend review/apply flow. The approved detailed design is in
`docs/superpowers/specs/2026-08-09-forward-engineering-design.md`.

## Trust and deployment boundaries

- Application PostgreSQL stores control-plane metadata; it must never be used
  as the DDL sandbox.
- Target credentials remain encrypted and are decrypted only inside guarded
  connection paths. Plans and queue payloads store identifiers and digests,
  never DSNs.
- The isolated validator must have no route or credentials to production.
- Live target operations retain SSRF target validation, verified TLS where
  configured, bounded timeouts and deterministic `search_path` handling.
- Other ContextualWisdomLab services integrate through versioned APIs; they do
  not share database ownership or bypass project authorization.

## References

Authoritative detail: [PRD](docs/PRD.md), [TRD](docs/TRD.md),
[ADR index](docs/adr/README.md), [v1 contract](docs/contracts/forward-engineering-v1.md),
[UML](docs/UML.md), and [metadata ERD](docs/DATA_MODEL.md). The
[Figma FigJam board](https://www.figma.com/board/MLWimuWoOWhatQ239QihfP) is a
non-authoritative visual companion.

PostgreSQL Global Development Group. (2026). *PostgreSQL 18 documentation:
Explicit locking*. https://www.postgresql.org/docs/18/explicit-locking.html

PostgreSQL Global Development Group. (2026). *PostgreSQL 18 documentation:
Transactions*. https://www.postgresql.org/docs/18/tutorial-transactions.html
