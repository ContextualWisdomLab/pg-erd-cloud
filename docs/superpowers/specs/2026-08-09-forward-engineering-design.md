# Forward Engineering Workflow Design

**Repository:** `ContextualWisdomLab/pg-erd-cloud`  
**Base:** `main@72afe6db712b145baaba084f64a1ff4fb36d9fd0`  
**Status:** Approved target architecture; Phase 1 control plane partially implemented
**Date:** 2026-08-09

## Implementation snapshot

Canonical product, technical, and runtime truth is maintained in
[`docs/PRD.md`](../../PRD.md), [`docs/TRD.md`](../../TRD.md), the
[`docs/adr/`](../../adr/README.md) decision set, and the
[`forward-engineering-v1` contract](../../contracts/forward-engineering-v1.md).
This document retains the approved end-state design and implementation order.

Implemented now: canonical model/revision persistence, `If-Match` concurrency,
strict snapshot adaptation for the proven subset, deterministic structured plan
compilation/persistence, plan bounds, fail-closed blockers, and the deployer
role on legacy persistent apply. Planned: plan retrieval, run/event persistence,
isolated dry run, live preflight, executor/recovery/convergence, and the frontend
workflow. The actual create route is
`POST /api/schema-models/by-project/{project_space_uuid}`; the project-nested
route below is a target compatibility shape, not current code.

## Problem

pg-erd-cloud can export DDL and snapshot-to-snapshot migration SQL, and the
backend exposes a conservative `apply-sql` endpoint. These pieces do not form a
working product flow:

- the ERD canvas emits quoted identifiers, foreign keys, and
  `CREATE INDEX CONCURRENTLY`, while the live-apply validator rejects quoted
  identifiers, foreign keys, comments, and concurrent indexes;
- the frontend never calls the live-apply endpoint;
- arbitrary client-supplied SQL is the wrong trust boundary for a graphical
  model editor;
- there is no persisted edited model, immutable migration revision, dry-run
  evidence, drift precondition, apply audit trail, or post-apply verification.

Connecting the existing button-sized pieces would therefore create a misleading
and unsafe feature. The product needs one server-authoritative workflow from an
edited model to a verified database state.

## Goals

1. Save an edited ERD as a project-scoped schema-model revision.
2. Compile an exact saved revision on the server into an immutable PostgreSQL
   migration plan and risk report.
3. Require a successful disposable-database execution dry run and live
   read-only preflight for the exact immutable plan before apply is enabled.
4. Detect live-schema drift before dry run and again immediately before apply.
5. Require explicit typed confirmation before queuing a live apply.
6. Execute live changes in the existing durable job queue with bounded timeouts,
   redacted errors, and retry-safe state transitions.
7. Reverse-engineer the database after commit and compare it with the desired
   model, preserving a verification snapshot and structural diff.
8. Preserve project membership and IDOR masking while adding an explicit live
   deploy capability; retain DSN encryption, SSRF-pinned target connections,
   CSRF protection, and exact-head test gates.

## Non-goals for the first production slice

- arbitrary SQL editing or execution;
- automatic rollback generation;
- data backfills or DML;
- heuristic rename detection (a remove/add remains explicit);
- Snowflake or MySQL live apply;
- online/non-transactional operations such as `CREATE INDEX CONCURRENTLY`;
- silently applying model features the compiler cannot represent;
- automatic or scheduled production apply.

Unsupported changes are reported as blocking findings. They are never omitted
from the preview while the UI still claims the desired model can be reached.

## Architecture

### 1. Models, immutable revisions, plans, and runs

Keep four responsibilities separate:

- `schema_model` is the project-scoped editable design identity and points to
  its current revision.
- `schema_model_revision` is immutable. It stores the canonical model JSON,
  revision number/hash, base snapshot, actor, and timestamp. Saving uses
  optimistic concurrency and creates a new row rather than rewriting history.
- `migration_plan` is an immutable compilation from one succeeded base snapshot
  and exact model revision to one project connection and schema scope. It stores
  base/target digests, detected PostgreSQL major version, compiler contract
  version, structured operations, read-only SQL preview, structural diff, risk
  report, blockers, and SHA-256 checksum.
- `migration_run` is one idempotent `dry_run` or `apply` attempt. It stores the
  plan/checksum, idempotency key, actor, state, observed live digest, evidence,
  verification snapshot/digest/diff, timestamps, and classified redacted error.

Each structured operation records transaction capability, expected lock level,
possible scan/rewrite, destructive or conversion risk, preconditions,
postconditions, and automatic rollback boundary. The compiler rejects
operations unavailable on the detected PostgreSQL version.

Add `migration_run_event` as an append-only audit record for queueing,
execution, confirmation, drift, commit, reconciliation, and verification.
Event payloads contain identifiers, hashes, counts, and sanitized diagnostics,
never DSNs or raw credential-bearing payloads. Queue payloads contain only a
`migration_run_uuid`, never DSNs or SQL.

Changing the model creates a new revision and supersedes prior plans for apply
run creation. Enqueue uses one compare-and-swap transaction against the model's
current revision and plan checksum: if a concurrent save wins first, enqueue
returns `409`; if enqueue wins first, the accepted run is frozen to the exact
confirmed plan and a later save creates a successor without changing that run.
Once created, a plan and its SQL/checksum never mutate. Further work after apply
starts from the verification snapshot and a successor model revision rather
than rewriting audit history.

### 2. Canonical model boundary

Create a shared backend canonicalizer for the PostgreSQL schema subset the
product can edit. It removes volatile capture metadata and OIDs, keys objects by
qualified name, preserves meaningful column order, and deterministically sorts
constraints and indexes. It validates identifiers, types, references,
duplicates, missing endpoints, unsupported expressions, and payload bounds.

The frontend introduces a `SchemaModel` domain with adapters
`snapshotToSchemaModel`, `schemaModelToGraph`, and `graphToSchemaModel`. React
Flow becomes a view/editing surface rather than the persistence or execution
contract. Conversion preserves non-editable metadata from the base snapshot and
replaces only objects controlled by the canvas. The backend treats every model
payload as untrusted, validates it independently, and owns canonicalization,
diffing, risk classification, compilation, and hashing.

The editable graph contract gains explicit `schema_name`, `relation_name`, and
stable client object IDs instead of interpreting React Flow node IDs or display
titles as database identity. Foreign-key edge data gains a separate constraint
name and ordered endpoint columns instead of parsing the human-readable label.
The snapshot contract also exposes structured columns for simple indexes while
retaining `index_def` for lossless reverse export. Expression, partial, and
otherwise opaque indexes remain visible/read-only; attempting to change one
produces a blocker instead of reparsing SQL text.

The current text `apply-sql` endpoint remains a compatibility surface but is
not used by the graphical workflow and is not broadened. New workflow execution
accepts a plan UUID and expected hash, never SQL from the browser.

### 3. Server-side migration compiler

Replace the split frontend-generator/live-validator contract with a structured
server compiler. Each statement has a kind, target objects, ordered SQL,
transactional flag, and risk linkage. The same operation objects drive SQL
rendering, executor dispatch, pre/postconditions, and the risk report so those
surfaces cannot disagree. The target compiler supports the model-editing subset
below. Phase 1 currently implements schema/table/column/nullability/type
operations and creation-time primary keys only; unique/FK/index/comment
operations remain unsupported and fail closed or produce explicit blockers.
When blocked, executable statements are empty while independent supported
deltas remain reviewable as digest-bound proposals:

- create missing schemas represented by the plan; never drop a schema
  automatically, and report desired schema removal as a blocker;
- create/drop tables;
- add/drop/alter columns and nullability;
- add/drop primary, unique, and foreign-key constraints when fully represented;
- create/drop ordinary PostgreSQL indexes with validated access-method tokens;
- table comments already represented by the snapshot model.

Identifiers are rendered with the backend's PostgreSQL quoting utility. SQL is
never reparsed to infer whether it is safe: executable statements originate
from validated structured objects. Executable plans avoid `IF EXISTS` and
`IF NOT EXISTS` where those clauses would mask precondition drift; existence is
proved structurally before execution. The plan compiler emits ordinary
transactional `CREATE INDEX`, not `CONCURRENTLY`; the risk report warns that it
can block writes. Online-index mode is deferred because PostgreSQL prohibits
`CREATE INDEX CONCURRENTLY` inside a transaction, so it cannot share the same
atomic rollback guarantee and a failed concurrent build can leave an invalid
index behind.

Every desired change must map to an executable statement or a blocking finding.
The plan cannot enter dry run while blocking findings exist.

### 4. Dry run and live preflight

Dry run never executes DDL on the live target, even inside a transaction.
Rollback would restore catalog state but would not undo the operational cost of
locks, scans, or table rewrites.

The `forward_dry_run` job performs two bounded checks:

1. **Disposable execution:** provision an isolated, short-lived PostgreSQL
   database matching the target major-version capability contract, materialize
   the complete operation-relevant dependency closure, execute the exact
   compiled transactional plan, reverse-engineer the result, and require the
   desired digest. The closure covers the editable table/column/PK/unique/FK,
   simple-index, and comment subset plus every supported dependency required to
   execute those operations. Affected views, triggers, checks/defaults,
   partitions, domains/extensions, operator classes, RLS, grants, or other
   dependencies that cannot be represented faithfully become blockers rather
   than being omitted. The database is destroyed after bounded evidence is
   persisted.
2. **Live read-only preflight:** re-introspect the target for the base digest and
   run operation-specific bounded read queries. Examples include existing NULL
   detection before `SET NOT NULL`, orphan detection before a foreign key, and
   explicit conversion probes before a type change. A timeout classifies an
   operation as unproven; it does not become success. Queries return only
   bounded existence/count evidence, and row values are neither persisted nor
   logged.

Live preflight is review evidence, not a concurrency guarantee. Apply repeats
every data-aware precondition after acquiring the operation's complete child,
parent, and dependency table set at the compiler-declared lock modes.

Deployment adds a dedicated migration-sandbox PostgreSQL service/credential
contract and isolated execution workload. Its runtime egress policy has no
route to production targets and it receives no target credentials; a separate
live-preflight worker retains only the required guarded target route. Production
operators can point the sandbox contract at an isolated cluster. The
application metadata database is never reused as a DDL sandbox.

### 5. Drift and concurrency contract

Create a canonical schema digest over all compiler-relevant objects and include
the PostgreSQL major version. The worker uses the same SSRF-guarded,
TLS-verified PostgreSQL connection path as reverse engineering.

- On dry run, introspect the live target and compare its digest with the plan's
  base digest before any preflight query. A mismatch records `drifted` with a
  structural diff and performs no DDL.
- On apply, repeat that comparison for the immutable plan checksum. Prior
  dry-run success is accepted only when its run references that same checksum
  and observed base digest; enqueue-time compare-and-swap decides whether a
  newer model revision has already superseded it.
- pg-erd-cloud writers are serialized with a deterministic target-database
  advisory lock. Bounded PostgreSQL `lock_timeout` and `statement_timeout`
  prevent indefinite blocking. External writers do not honor advisory locks;
  the worker therefore starts the transaction, takes affected-object locks in
  deterministic qualified-name order, and reruns schema and data-aware
  preconditions on that same connection before executing. The selected lock
  modes must prevent concurrent `INSERT`/`UPDATE` from invalidating NULL,
  foreign-key, or conversion probes until commit. Conflicting external DDL/DML
  must fail or block within the configured timeout and produce a redacted
  non-success result.

Apply executes the ordered transaction-capable statement plan in one
transaction and commits only if every statement and postcondition succeeds.
Non-transactional operations are blockers in this slice.

### 6. Durable apply and verification

Dry run and live apply both run as durable jobs. The API persists a
`migration_run` and queue record before external I/O, returns `202`, and the
frontend polls the run. This keeps long preflight, lock waits, disconnects, and
process restarts outside the HTTP request lifetime.

Dry-run states are:

`queued -> sandbox_running -> live_preflight_running -> passed | drifted | failed`

Apply states are:

`queued -> applying -> reconciling -> verifying -> verified | drifted_no_apply | not_applied | verification_failed | failed_rolled_back | applied_with_drift | outcome_unknown`

Compare-and-swap transitions plus a unique idempotency key allow one winner for
concurrent submissions. Apply requires the explicitly referenced passed dry run
for the same immutable plan checksum and observed base digest, then repeats
schema and data-aware preconditions regardless. After apply begins, the job is
never automatically replayed because a process failure can make commit outcome
ambiguous.

Terminal states distinguish whether live DDL ran:

- `drifted_no_apply`: live base no longer matches; no DDL ran;
- `failed_rolled_back`: the live transaction rolled back;
- `not_applied`: reconciliation after a lost acknowledgement proves the exact
  base digest still exists;
- `verification_failed`: commit succeeded but reverse verification could not
  finish, so the UI must not describe the database as unchanged;
- `applied_with_drift`: commit succeeded and verification found a residual
  diff;
- `outcome_unknown`: commit acknowledgement or reliable reconciliation evidence
  is unavailable; the system forbids replay and makes no applied/not-applied
  claim.

After commit, the worker reverse-engineers the same connection and schema filter,
persists a normal `SchemaSnapshot`/`SchemaSnapshotData` verification record, and
compares its canonical digest with the desired digest. A matching digest marks
the run `verified`. Reconciliation after an uncertain post-commit failure first
introspects the target: desired digest becomes `verified`, exact base digest
becomes `not_applied`, and unavailable evidence or any third digest becomes
`outcome_unknown`. `applied_with_drift` is used only when commit success is
known and post-commit verification proves a residual diff. None of these paths
automatically replays DDL.

### 7. API contract

All model, plan, and run reads require project membership. Model creation,
revision, planning, and dry run require `editor`. Live apply requires the new
`deployer` capability, inherited by project owners; project role ordering is
`viewer < editor < deployer < owner`. Non-members receive the repository's
uniform not-found behavior. Mutations retain CSRF and credentialed-request
requirements. Planning also proves that the connection and succeeded base
snapshot belong to the same project and that the base snapshot was captured
from that exact connection.

The legacy `apply-sql` request/response shape remains compatible, but
`dry_run=false` is tightened to the same `deployer` capability so it cannot
bypass the workflow's live-mutation boundary. Editors retain its default
rollback-only behavior. Project responses expose the current user's capability
so the frontend can gate controls without treating UI gating as authorization.

- **Current:** `POST /api/schema-models/by-project/{project_space_uuid}` creates
  a model from a succeeded snapshot or an explicit blank model.
- **Target compatibility shape:** `POST /api/projects/{project_uuid}/schema-models`.
- `GET /api/schema-models/{model_uuid}`
  returns the model and current immutable revision.
- `PUT /api/schema-models/{model_uuid}` with `If-Match`
  validates the edited model and creates a new revision; conflicts return `409`.
- `POST /api/schema-model-revisions/{revision_uuid}/migration-plans`
  binds an exact connection/base snapshot and returns an immutable compiled
  preview/checksum.
- **Planned:** `GET /api/migration-plans/{plan_uuid}`
  returns structured operations, SQL preview, risk, blockers, and hashes.
- **Planned:** `POST /api/migration-plans/{plan_uuid}/dry-runs`
  requires `Idempotency-Key` and the plan checksum, creates a `dry_run`, and
  returns `202` with its run UUID.
- **Planned:** `POST /api/migration-plans/{plan_uuid}/apply-runs`
  requires `Idempotency-Key`, plan checksum, matching passed dry-run UUID,
  typed connection-name confirmation, and destructive acknowledgement when
  applicable; it returns `202` with its run UUID.
- **Planned:** `GET /api/migration-runs/{run_uuid}`
  returns polling state and bounded evidence, including verification snapshot
  and residual diff when terminal.

Stale revisions/checksums return `409`. Invalid models return structured `422`
findings. Blocking compiler findings return a normal preview with
`can_dry_run=false`. Database diagnostics are classified and DSN-redacted.

### 8. Frontend workflow

Preserve the existing canvas, toolbar, modal language, spacing, typography, and
component patterns. This is a functional extension, not a redesign.

Add one `DB 반영` action in the authenticated editable canvas. It opens an
accessible forward-engineering modal with progressive states:

1. **변경안 저장:** name the model and save the current edited canvas as an
   immutable revision. A saved model can be reopened through the
   same graph-building primitives through a dedicated desired-schema adapter;
   it does not manufacture database OIDs.
2. **변경 검토:** select the exact connection and succeeded base snapshot,
   compile an immutable plan, and show target scope, base/target hashes, risk
   counts, blocking findings, object-level changes, and read-only
   server-generated SQL.
3. **Dry run:** execute against the disposable sandbox, then run live read-only
   preflight; show each evidence source, redacted failure, or drift details. A
   new model revision visibly supersedes the reviewed plan and its dry run.
4. **실제 적용:** require typing the exact connection name and reconfirm the
   destructive/warning counts. A destructive plan also requires a separate
   explicit acknowledgement. The action queues once and cannot be double
   submitted.
5. **재검증:** poll the run and show the verification snapshot, exact-match
   result, or residual drift. Distinguish rolled-back failure from
   committed-but-unverified states.

Editors can save, review, and dry-run. The live apply control requires the
project's server-reported `deployer` capability; insufficient capability is
explained in place and remains enforced by the API.

Focus is trapped inside the modal; headings, risk summaries, errors, progress,
and terminal results have appropriate accessible names/live regions. Escape and
cancel work before apply is queued. Closing the modal never cancels an already
queued run. Demo mode allows preview-only behavior and clearly disables
live dry run/apply rather than simulating a successful production mutation.

The existing `ExportModal` remains copy/download/share-only; live mutation is
kept in a separate `ForwardEngineeringModal`. Verification polling uses a
dedicated verification snapshot ID and never reuses the editor's loaded
snapshot state, so an in-progress check cannot overwrite unsaved canvas edits.

## Error handling and operational safeguards

- Bound plan/model size and statement count before persistence or target DB I/O.
- Store migration-sandbox credentials in the repository's credential-registry
  boundary; do not add a new runtime `os.getenv()`/raw-environment secret path.
- Redact DSN-derived values at every worker/API boundary.
- Never log complete desired-schema JSON, raw SQL batches, or connection
  secrets; log plan UUID, hash prefix, state, statement count, and durations.
- Use one active apply job per plan hash and reject duplicate queue requests.
- Persist actor, confirmation hash, and event timestamps for auditability.
- Expose metrics for plan outcomes and stage durations without high-cardinality
  identifiers.
- Do not weaken the existing `apply-sql` validator, branch protections,
  dependency scanning, or 100% production coverage contract.

## Test strategy

Implementation follows red-green-refactor in small vertical slices.

### Backend unit and contract tests

- canonicalization and digest stability across volatile OIDs/order, plus
  sensitivity to every compiler-relevant mutation and PostgreSQL major version;
- desired-model validation for duplicates, invalid references, unsupported
  expressions, identifiers, payload and statement bounds;
- literal expected SQL for each compiler operation, safe quoting, stable order,
  risk linkage, and blocking-findings completeness;
- the mandatory contract that every generated executable plan is accepted by
  the structured executor without browser-supplied SQL parsing;
- immutable model revision/plan checksums and supersession after every editable
  input change;
- API role/IDOR/CSRF behavior, public-share mutation denial, revision/checksum
  tampering, editor-versus-deployer capability, typed confirmation, duplicate
  queue prevention, and redacted failures;
- job state transitions, sandbox lifecycle, live read-only preconditions,
  timeouts, drift checks, rollback, commit,
  post-commit verification, and retry-after-uncertain-commit recovery.

### PostgreSQL integration tests

Use an ephemeral PostgreSQL target to prove that:

- dry run executes only in the sandbox and leaves the live target unchanged;
- sandbox execution reaches the desired digest and cleans up its disposable
  database on success and failure;
- apply produces the desired schema and a matching verification snapshot;
- a concurrent base change blocks execution as drift;
- concurrent `INSERT`/`UPDATE` cannot invalidate apply-time data preconditions
  after the compiler-declared locks are held;
- statement failure rolls back earlier statements;
- quoted/mixed-case/reserved identifiers represented by the model remain safe;
- foreign keys and indexes generated by the model execute under the same
  structured contract;
- lock and statement timeouts terminate with a classified, redacted result;
- concurrent idempotent apply requests produce one winner;
- a model-save/apply-enqueue race either returns `409` before acceptance or
  freezes the exact accepted plan; stale DDL never wins silently;
- crash-after-commit reconciliation verifies or reports drift without replay.

### Frontend tests

- graph-to-schema-model conversion preserves untouched base metadata and
  reflects table, column, key, relationship, and index edits;
- model dirty/save state and `409` optimistic-concurrency recovery;
- typed API clients send CSRF-protected exact-hash requests and validate response
  shapes;
- modal keyboard/focus behavior, loading, errors, drift, risk review, typed
  confirmation, stale revision, double-submit prevention, polling, and all
  terminal states;
- demo mode remains explicit preview-only behavior.

### End-to-end acceptance

Against the composed app and a disposable PostgreSQL target: reverse a schema,
edit the ERD, save a plan, review risk/SQL, dry-run, explicitly apply, wait for
reverse verification, and assert an empty residual diff. Repeat with injected
live drift and assert that no plan statement executes.

## Acceptance criteria

The feature is complete only when all of the following are true on the exact PR
head:

1. An edited canvas can be persisted and reopened as a versioned schema model.
2. The server preview contains every supported change and blocks every
   unsupported change without silent omission.
3. The UI cannot apply a stale, undry-run, drifted, or unconfirmed revision.
4. Dry run demonstrably executes in an isolated PostgreSQL sandbox while the
   live target receives only bounded read-only preflight queries.
5. Apply is durable, single-queued, transactional, and retry-safe.
6. Post-apply reverse engineering persists evidence and reports exact match or
   residual drift truthfully.
7. Existing exports remain backward compatible; the raw `apply-sql` payload is
   unchanged and its live (`dry_run=false`) authorization is intentionally
   tightened to `deployer`.
8. Backend mypy/pytest/coverage, frontend typecheck/tests/coverage/build,
   security scans, and browser workflow verification pass on the exact head.

## References to ground implementation

Primary PostgreSQL contracts:

- PostgreSQL Global Development Group. (n.d.). [Transactions](https://www.postgresql.org/docs/18/tutorial-transactions.html).
- PostgreSQL Global Development Group. (n.d.). [CREATE INDEX](https://www.postgresql.org/docs/18/sql-createindex.html).
- PostgreSQL Global Development Group. (n.d.). [ALTER TABLE](https://www.postgresql.org/docs/18/sql-altertable.html).
- PostgreSQL Global Development Group. (n.d.). [Explicit locking](https://www.postgresql.org/docs/18/explicit-locking.html).
- PostgreSQL Global Development Group. (n.d.). [Client connection defaults](https://www.postgresql.org/docs/18/runtime-config-client.html).
- PostgreSQL Global Development Group. (n.d.). [System information functions and decompiled definitions](https://www.postgresql.org/docs/18/functions-info.html).
- PostgreSQL Global Development Group. (n.d.). [`pg_index`](https://www.postgresql.org/docs/18/catalog-pg-index.html).

Schema-evolution research:

- Eckwert, T., Guckert, M., & Taentzer, G. (2025). EvolveDB: Evolving
  relational database schemas in a model-driven way. *Software and Systems
  Modeling*. [https://doi.org/10.1007/s10270-025-01341-x](https://doi.org/10.1007/s10270-025-01341-x)
- Curino, C. A., Moon, H. J., & Zaniolo, C. (2008). Graceful database schema
  evolution: The PRISM workbench. *Proceedings of the VLDB Endowment, 1*(1),
  761-772. [https://doi.org/10.14778/1453856.1453939](https://doi.org/10.14778/1453856.1453939)
- Rae, I., Rollins, E., Shute, J., Sodhi, S., & Vingralek, R. (2013). Online,
  asynchronous schema change in F1. *Proceedings of the VLDB Endowment, 6*(11),
  1045-1056. [https://doi.org/10.14778/2536222.2536230](https://doi.org/10.14778/2536222.2536230)
- Hu, T., Wang, T., & Zhou, Q. (2022). Online schema evolution is (almost) free
  for snapshot databases. *Proceedings of the VLDB Endowment, 16*(2), 140-153.
  [https://doi.org/10.14778/3565816.3565818](https://doi.org/10.14778/3565816.3565818)

PRISM, F1, and the Hu et al. paper are link-only because their publication
terms do not support commercial-repository redistribution without additional
permission. EvolveDB is CC BY 4.0, but the implementation PR will prefer a DOI
link and relevance summary unless its PDF attribution and third-party material
can be verified completely.
