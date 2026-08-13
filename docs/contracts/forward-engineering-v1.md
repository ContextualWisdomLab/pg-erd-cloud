# Forward-engineering v1 contract

- **Contract status:** Partially implemented
- **Release status:** Not production-ready
- **Compiler identifier:** `pg-erd-forward/v1`
- **Canonical model format:** `format_version: 1`
- **Supported server majors:** PostgreSQL 14 through 18
- **Last verified against working tree:** 2026-08-09

This document separates current repository behavior from the accepted release
contract. The words **Implemented**, **Partially implemented**, **Planned**, and
**Rejected** are normative status labels. A planned route, entity, or state does
not exist merely because it appears here.

Repository code, tests, this contract, and repository Mermaid diagrams are the
authoritative implementation sources. The
[FigJam board](https://www.figma.com/board/MLWimuWoOWhatQ239QihfP) is a
non-authoritative visual companion.

## 1. Scope and release boundary

Forward engineering v1 turns an edited PostgreSQL schema model into a
server-compiled immutable plan, proves that exact plan outside production,
performs live read-only preflight, obtains an evidence-bound deployer approval,
applies one transactional segment, and re-introspects the target to prove
convergence.

Current code implements only the first control-plane slice:

- **Implemented:** canonical model validation/digest; persisted model identities
  and immutable revisions; optimistic revision API; deterministic structured
  plan compilation/persistence and authenticated immutable-plan retrieval;
  project `deployer` role; deployer gating on the legacy persistent `apply-sql`
  path.
- **Partially implemented:** fail-closed snapshot-to-model conversion and the
  supported compiler subset. Known gaps are listed in section 6.
- **Partially implemented:** durable run/event persistence, exact state
  validation, hashed idempotency keys, bounded evidence canonicalization, and
  atomic optimistic compare-and-swap transition/event persistence plus an
  internal database-selected dry-run creation writer, cancellation intent, and
  authenticated integrity-checked run polling and editor-authorized cancellation
  API, plus editor-authorized exact-digest/idempotency-bound dry-run creation;
  the terminal preflight CAS requires and persists the canonical observed base
  digest, revalidates plan integrity, and enforces exact `passed` match versus
  `drifted` mismatch semantics. `complete_live_preflight` validates the exact
  bounded executor-result shape and server-derives `passed`, `drifted`, or
  `failed`; a caller cannot select the state, event type, or digest. No worker
  execution authority exists yet. The
  execution-neutral consumer contract is **Implemented**; consumer-to-attempt
  binding is **Implemented** without plan, credential, or SQL authority.
  When attempt acquisition finds a persisted cancellation intent, the adapter
  locks the run and records the terminal `cancelled` acknowledgement before the
  exact signal is acknowledged. A redelivered already-terminal run is settled
  without replaying sandbox or live-preflight work.
  Application startup wiring and worker execution remain **Planned**.
- **Partially implemented:** the live-preflight primitive compiles the current
  structured data preconditions into bounded boolean-only reads and executes
  them in one timed read-only transaction. `execute_bound_live_preflight`
  additionally binds a caller-owned fresh snapshot callback and those checks
  to that same transaction, returning its canonical digest and plan-base match.
  `complete_live_preflight` revalidates the stored run and immutable plan, then
  requires the result's exact `(statement_index, precondition_index, kind)` set
  to equal every persisted plan precondition before producing a bounded
  aggregate-evidence CAS. Missing, extra, duplicate, or kind-mismatched checks
  fail closed. These primitives have no credential, worker identity,
  durable-attempt acquisition, or DDL authority.
- **Partially implemented:** the isolated-dry-run execution core verifies one
  signed v1 plan, compatible PostgreSQL major, strict materialized base,
  all-transactional statement list, rollback boundary, and target-digest
  convergence. `complete_isolated_dry_run` accepts only its exact bounded
  success result, revalidates plan provenance, and derives the fixed
  `live_preflight_running` CAS. It does not provision, isolate, materialize,
  clean, or bind a durable worker attempt.
- **Implemented:** exact deployer-confirmed, execution-free apply-intent
  creation binds the current model revision, immutable plan, passed dry run,
  observed base digest, confirmation digest, actor, and idempotency key without
  creating dispatch or DDL authority.
- **Partially implemented:** browser plan review, dry-run submission, durable run
  polling/status/audit, and exact-version cancellation intent surfaces exist.
  They remain bounded intent/review surfaces and provide no credential or SQL
  authority.
- **Planned:** deployed isolated sandbox lifecycle, credential binding,
  application worker execution, live apply dispatch/executor, apply-time
  fingerprint revalidation, deployed in-flight cancellation, apply recovery,
  post-apply convergence, and the complete browser apply/recovery workflow.
- **Rejected for v1:** browser-authored SQL in the graphical workflow,
  production DDL rollback as dry-run evidence, DML/backfills, heuristic rename
  inference, automatic rollback generation, scheduled apply, MySQL/Snowflake
  live apply, and non-transactional/online index execution.

## 2. Requirement and invariant IDs

| ID | Normative requirement | Status |
|---|---|---|
| FE-INV-001 | Graphical clients submit semantic model intent; only the server renders executable SQL. | Partially implemented |
| FE-INV-002 | A model revision is canonical, content-digested, and append-only through the API. | Implemented |
| FE-INV-003 | A plan binds one revision, project, connection, succeeded base snapshot, compiler version, base/target digests, actor, and expiry. | Implemented |
| FE-INV-004 | Every admitted semantic difference becomes an operation or blocker; blockers suppress executable statements while supported independent deltas remain reviewable as proposals. | Implemented for the current admitted subset |
| FE-INV-005 | Dry run executes DDL only in an isolated sandbox; the live dry-run phase is read-only. | Partially implemented: isolated execution core plus `complete_isolated_dry_run` success-result CAS and bounded live-read primitive; deployed isolation, sandbox lifecycle, and workers Planned |
| FE-INV-006 | Dry run and apply re-introspect the target and require the bound base fingerprint before DDL. | Partially implemented for the isolated execution core; durable worker binding and apply remain Planned |
| FE-INV-007 | Apply repeats data preconditions after deterministic locks are held on the execution connection. | Planned |
| FE-INV-008 | V1 applies exactly one all-transactional segment; a failure rolls it back. | Planned |
| FE-INV-009 | A run is durable and idempotent; an apply is never automatically replayed after `applying` begins. | Partially implemented |
| FE-INV-010 | Live apply requires `deployer`, exact-plan confirmation, a matching passed dry run, and separate destructive acknowledgement when applicable. | Partially implemented |
| FE-INV-011 | Queue/event/browser payloads never contain a DSN, decrypted secret, or raw client SQL. | Partially implemented |
| FE-INV-012 | Only a persisted verification snapshot matching `target_digest` may produce `verified`. | Planned |
| FE-INV-013 | Cross-project resource identities are uniformly masked as not found. | Partially implemented |
| FE-INV-014 | Unknown fields, object kinds, operation kinds, and compiler versions fail closed. | Partially implemented |

No production-readiness claim is permitted while any FE-INV requirement is
Partially implemented or Planned.

## 3. Current persisted resources

### `schema_model` — Implemented

Project-scoped editable identity. `current_revision_number` points to the
current immutable revision. `(project_space_uuid, model_name)` is unique.

### `schema_model_revision` — Implemented

Append-only through current APIs. It stores `revision_number`,
`revision_digest`, canonical `model_json`, optional
`base_schema_snapshot_uuid`, actor, and creation time. The database enforces a
unique `(schema_model_uuid, revision_number)` pair. Immutability is currently an
application/API rule rather than a database update-prevention trigger.

### `migration_plan` — Implemented

Created by the server from one stored revision and one succeeded snapshot bound
to the same project and exact connection. It stores `compiler_version`,
`base_digest`, `target_digest`, `statement_digest`, `plan_json`, actor, and a
24-hour `expires_at`. There is no update route. Internal dry-run creation
rejects expired plans. Creation-time maintenance deletes only derived plans
that expired at least 30 days earlier, belong to the authorized project, and
have no durable `MigrationRun` history; plans with run evidence are retained.

### `migration_run`, dispatch, attempt, and event — Partially implemented

The ORM classes and Alembic revisions `0010_migration_run`,
`0011_migration_run_attempt`, `0012_apply_intent_confirmation`, and
`0013_migration_run_cancellation` persist an
idempotent run identity, optional passed-dry-run/confirmation bindings, one
identifier-only transactional outbox row for executable dry runs, and an
append-only per-run event sequence. The implemented dry-run writer adds exactly
one outbox row for each new run; apply-intent creation adds none. The database
unique constraint enforces at most one dispatch per run.
The row admits only `isolated_dry_run` and binds pending/published state to its
publication timestamp without containing a DSN, SQL, or plan payload. Database
checks bound
run kind, state, state version, event type, before/after state tokens, event
sequence, predecessor presence, and every persisted lowercase SHA-256 digest
shape (idempotency, plan, request, observed base, chain link, and run anchor). A
project/run-kind idempotency
key is unique independently of plan identity, while `request_digest` preserves
the effective request needed to reject same-key/different-request reuse.
`app.forward.migration_run` defines the exact state graph, hashes bounded
idempotency keys, deterministically binds project, plan, run kind, plan digest,
and requesting actor in versioned `request_digest`, and rejects raw SQL,
credential-bearing fields, or PostgreSQL connection-string values from bounded
evidence JSON. The internal cancellation-intent writer and editor-authorized
`POST /api/migration-runs/{migration_run_uuid}/cancel` route are
**Implemented**. Public dry-run creation is **Implemented**. Public apply intent
creation is **Implemented**. Apply intent creation binds a deployer, exact plan digest,
same-plan passed dry-run UUID/base digest, exact typed target connection name,
and the plan's exact destructive-confirmation requirement. The API locks the
plan's schema-model row `FOR UPDATE` and rejects `stale_revision` unless the
plan-bound revision UUID, number, target/revision digest, model, and project
still match the current row. It creates no
dispatch, signal, credential access, SQL execution, or executor authority.
Lock-scoped due-order outbox claiming,
attempt-bound publish-state CAS, and the opt-in scheduled relay lifecycle are
**Implemented**. Atomic UUID-only ready-to-processing claim, expiry reclaim,
exact lease renewal, acknowledgement, and retry release use an exact
lease-token so a stale claimant cannot extend or complete a successor lease.
The execution-neutral consumer
contract is **Implemented**: it invokes one injected handler with the exact
signal claim (the run UUID plus its opaque lease-token), acknowledges only
after success, releases the exact lease on a sanitized failure, and fails
closed when either completion loses lease ownership. The ready-queue payload
remains UUID-only; the token is processing metadata, not execution authority.
An expired signal owner cannot renew, and renewal never shortens an existing
expiry. Automatic heartbeat is
**Implemented**: the consumer renews while its injected handler runs, cancels
the handler when exact renewal is lost, and never acknowledges that loss as
success. A separate DB-durable attempt contract is **Implemented**: acquisition
serializes on an executable uncancelled dry run, stores only hashes of bounded
worker identity and the opaque signal token, permits one active owner, abandons
only an expired owner, and creates a monotonic attempt number. Renewal and
finish are exact-token CAS operations; renewal also requires an executable run,
and neither operation can revive or complete an expired attempt.
Consumer-to-attempt binding is **Implemented** by an execution-neutral adapter:
it commits acquisition before invoking an injected handler, renews the exact
attempt through fresh metadata transactions, cancels work on lease loss, and
finishes the exact owner before the outer consumer may acknowledge the signal.
If acquisition rejects a cancelled run, the adapter locks and reloads the row,
records an empty-evidence `cancellation_acknowledged` transition to terminal
`cancelled`, and only then permits exact signal acknowledgement. If the row is
already terminal, redelivery is acknowledged without reacquiring an attempt or
replaying sandbox/preflight execution. In either settlement path, a surviving
active attempt is locked and marked `abandoned` before acknowledgement so crash
recovery cannot leave a durable owner active forever.
Application startup wiring, credentials, and worker execution remain
**Planned**. The bounded
one-attempt publisher is **Implemented**: it emits only `migration_run_uuid`
to a dedicated Valkey sorted-set key, then acknowledges only the exact claimed
attempt in the same caller-owned transaction. Deployed sandbox/preflight worker
startup, in-flight process cancellation, apply, reconciliation, and verification
remain **Planned**.

Each event stores `previous_event_digest` and `event_digest`; the run stores
`latest_event_digest`. Contract `migration-run-event/v1` hashes the run UUID,
sequence, type, before/after state, canonical evidence, actor, normalized UTC
timestamp, and predecessor. Genesis has no predecessor; later events require a
64-character lowercase SHA-256 predecessor. The run CAS also matches the prior
anchor. Retrieval recomputes every link and the terminal anchor, returning a
sanitized `409` on mismatch; it also requires the exact genesis event and
replays every ordinary or same-state cancellation transition through the v1
state graph. The persisted `cancellation_requested` flag must exactly match one
cancellation event; a missing, duplicate, or contradictory event fails closed.
This is tamper-evidence, not a signature or a
guarantee against an actor that can rewrite the entire metadata database.

`create_migration_run` is the implemented internal creation boundary. It
verifies stored-plan integrity and expiry, rejects blocked plans and all apply
requests, hashes the opaque idempotency key, and uses
`uq_migration_run__idempotent_action` as the PostgreSQL concurrency winner.
Only a new winner receives the sequence-one `run_queued` event and one
`migration_run_dispatch` row in the same caller-owned transaction; a
duplicate is reused only when its versioned request digest is identical. The
function does not commit, publish the outbox, or signal a worker.
`claim_one_migration_dispatch` selects one due pending row with
`FOR UPDATE SKIP LOCKED`, increments its attempt in the caller-owned
transaction, and returns only identifiers plus fixed kind and attempt.
`mark_migration_dispatch_published` CAS-updates that exact attempt.
`publish_one_migration_dispatch` keeps the caller-owned transaction open across
claim, UUID-only publication on the dedicated migration-run Valkey key, and
acknowledgement. A publication failure raises before acknowledgement so the
caller can roll the claim back. The sorted-set member is the run UUID, making
an ambiguous retry idempotent at the signal layer. The opt-in scheduled relay
lifecycle is **Implemented**: it opens one fresh metadata transaction per
claim, commits only after exact-attempt acknowledgement, rolls an exception
back through the transaction context, sleeps at a bounded positive interval
after empty or failed iterations, and cancels cleanly with the application.
It refuses startup unless the Valkey signal backend is configured. The
execution-neutral consumer contract is **Implemented**; consumer-to-attempt
binding is **Implemented** without plan, credential, or SQL authority.
Application startup wiring and worker execution remain **Planned**. The consumer and lease
primitives never load a plan, target credential, SQL batch, or row value.

`transition_migration_run` validates event metadata and evidence before any
database access, reads the current run identity, and executes one optimistic
update matching UUID, run kind, state, expected state version, and prior event
digest. Only the CAS
winner appends `migration_run_event` with the next sequence number. The caller
owns the transaction, so an event insert failure rolls the state update back.

The **Implemented** internal `request_migration_run_cancellation` writer does
not invent a synthetic state. It CAS
updates `cancellation_requested` and `state_version` while matching the exact
UUID, kind, state, prior version, and false cancellation flag, then appends a
same-state event at the new sequence. Repeated intent is idempotent; terminal,
missing, invalid, and stale runs fail closed.

The attempt-bound consumer acknowledgement is also **Implemented** for dry-run
states and queued apply intent. It requires the persisted intent, fixed
`cancellation_acknowledged` event type, empty evidence, no actor, and the exact
state-version/flag CAS. Cancelling from `queued` sets `finished_at` without
claiming `started_at`; `cancelled` is terminal and makes no live-DDL claim.

The public cancellation route requires a strict positive
`expected_state_version`, editor authority, and the exact run UUID. It binds the
middleware-selected request ID and actor to the appended evidence, commits only
after the CAS writer succeeds, returns `202`, masks nonmembers as `404`, and
uses the stable sanitized run-action error envelope described in section 9.

## 4. Canonical model JSON

`app.forward.schema_model.canonicalize_schema_model` is the current authority.
Canonical JSON has this shape:

```json
{
  "format_version": 1,
  "postgresql_major": 16,
  "schemas": [
    {
      "schema_name": "public",
      "tables": [
        {
          "table_name": "account",
          "comment": null,
          "columns": [
            {
              "column_name": "account_id",
              "data_type": "uuid",
              "nullable": false,
              "ordinal_position": 1,
              "comment": null
            }
          ],
          "primary_key": {
            "constraint_name": "account_pkey",
            "columns": ["account_id"],
            "deferrable": false,
            "initially_deferred": false
          },
          "unique_constraints": [],
          "foreign_keys": [],
          "indexes": [],
          "unsupported_features": []
        }
      ]
    }
  ]
}
```

Normative validation:

- payload size is at most 2 MiB at the current model API boundary;
- `format_version` equals `1` and PostgreSQL major is 14–18;
- identifiers are non-empty, NUL-free, and at most 63 UTF-8 bytes; exact case,
  whitespace, Unicode, reserved words, and quotes are preserved;
- schema names, table names, column names, column ordinals, and primary-key
  columns are unique in their respective scopes;
- every primary-key column is explicitly `nullable=false` so catalog
  re-introspection cannot introduce an unrequested nullability delta;
- column ordinals are positive integers and are semantically meaningful;
- only the canonicalizer's allow-listed PostgreSQL data types are admitted;
  aliases normalize to `pg_catalog.format_type` spelling and non-convergent
  `smallserial`/`serial`/`bigserial` pseudo-types are rejected;
- defaults, identity/generated columns, unique/foreign-key constraints,
  indexes, and `unsupported_features` are currently rejected when non-empty;
- unknown fields fail closed, except explicitly named volatile capture fields,
  which are discarded;
- schemas and tables are sorted by exact name; columns are sorted by ordinal and
  name; JSON is hashed with sorted keys, compact separators, and UTF-8.

The canonicalizer accepts table/column comments, but compiler v1 does not emit
`COMMENT` statements. Comment additions, removals, or changes therefore produce
explicit blockers and suppress all executable statements.

## 5. Current HTTP API contract

All routes use the repository's current authenticated, credentialed API
boundary. Unless a route decorator states otherwise, successful FastAPI
mutations currently return `200`, not `201`.

| Method and current route | Request | Success response | Authority | Status |
|---|---|---|---|---|
| `POST /api/schema-models/by-project/{project_space_uuid}` | `SchemaModelCreateIn` | `SchemaModelDetailOut`, `200` | editor+ | Implemented |
| `GET /api/schema-models/{schema_model_uuid}` | none | current `SchemaModelDetailOut`, `200` | member | Implemented |
| `PUT /api/schema-models/{schema_model_uuid}` | `SchemaModelReviseIn`; required `If-Match` | successor `SchemaModelDetailOut`, `200` | editor+ | Implemented |
| `POST /api/schema-model-revisions/{schema_model_revision_uuid}/migration-plans` | `MigrationPlanCreateIn` | `MigrationPlanOut`, `200` | editor+ | Implemented |
| `GET /api/migration-plans/{migration_plan_uuid}` | none | current `MigrationPlanOut`, `200` | member | Implemented |
| `POST /api/connections/{db_connection_uuid}/apply-sql` | legacy `ApplySqlIn` | `ApplySqlOut`, `200` | editor for rollback-only; deployer for persistent apply | Implemented legacy compatibility only |

`SchemaModelCreateIn` contains `model_name`, `model_json`, and optional
`base_schema_snapshot_uuid`. `SchemaModelReviseIn` contains `model_json` and
optional `base_schema_snapshot_uuid`. `SchemaModelDetailOut` contains model and
current revision UUIDs, model name, revision number/digest, canonical model JSON,
and optional base snapshot UUID.

`MigrationPlanCreateIn` contains `db_connection_uuid` and
`base_schema_snapshot_uuid`. The server additionally receives the exact model
revision UUID in the route. `MigrationPlanOut` contains plan/base/target
digests, compiler version, `can_dry_run`, destructive-confirmation flag,
structured executable statements, review-only `proposed_statements`, blockers,
risk summary, and expiry.

The immutable preview exposes project, model-revision, connection,
base-snapshot, snapshot-contract, PostgreSQL-major, creator, and creation-time
bindings so a client can review the exact stored execution identity rather than
infer authority from mutable UI state.

Current route truth takes precedence over the older design-spec spelling
`POST /api/projects/{project_uuid}/schema-models`. That project-nested alias is
**Planned**, not implemented; the team must choose one canonical release path
or supply an explicit compatibility alias before public v1 stabilization.

## 6. PostgreSQL support matrix

| Desired change / object | Current canonical/snapshot boundary | Current compiler | Release-v1 disposition |
|---|---|---|---|
| Create schema | Admitted | `create_schema` | Implemented control plane; execution Planned |
| Remove schema | Admitted model difference | `schema_removal_unsupported` blocker | Implemented blocker |
| Create table | Admitted subset | `create_table` | Implemented control plane; execution Planned |
| Drop table | Admitted subset | `drop_table`, destructive | Implemented control plane; execution Planned |
| Add column | Admitted subset | `add_column`; required/no-default adds `table_is_empty` precondition | Implemented plan; bounded live-read `table_is_empty` precondition primitive and completion CAS are Implemented; durable worker binding and apply remain Planned |
| Drop column | Admitted subset | `drop_column`, destructive | Implemented control plane; execution Planned |
| Change data type | Catalog-spelling allow-list; aliases normalize; serial pseudo-types reject | `alter_column_type`, conservative destructive/data-loss/scan/rewrite risk and castability precondition | Implemented plan; generic isolated executor core plus bounded live-read `castable_values` precondition primitive and completion CAS are Implemented; durable worker binding and type-change dependency/privilege/apply proof remain Planned |
| Set/drop nullability | Admitted | `set_not_null` / `drop_not_null` | Implemented plan; bounded live-read `no_null_values` precondition primitive and completion CAS are Implemented for set-not-null; durable worker binding and apply remain Planned |
| Primary key on a new table | Admitted | Included in `CREATE TABLE`, preserving ordered columns and deferrability | Implemented plan |
| Change existing primary key | Admitted | `primary_key_change_unsupported` blocker | Implemented blocker |
| Table/column comment change | Admitted and digest-affecting | Explicit comment blocker; no partial statements | Implemented blocker |
| Existing/non-append column order change | Admitted and digest-affecting | `column_order_change_unsupported` blocker | Implemented blocker |
| Unique or foreign-key constraint | Non-empty collections rejected | Not compiled | Rejected for current slice; future support needs a versioned contract |
| Secondary or expression/partial index | Snapshot/model rejected | Not compiled | Rejected for current slice |
| Default, identity, generated column | Model rejects; snapshot mapping must be proven lossless | Not compiled | Rejected for current slice |
| Views, triggers, functions, RLS, policies, grants, partitions, domains, extensions | Not represented losslessly | Not compiled | Rejected; detected dependencies must block planning |
| `CREATE INDEX CONCURRENTLY` or other non-transactional DDL | Not admitted | Not compiled | Rejected for v1 |
| DML or backfill | Not a model operation | Not compiled | Rejected for v1 |
| MySQL/Snowflake live apply | No forward model contract | No compiler | Rejected for v1 |

Current `snapshot_to_schema_model` admits primary-key backing indexes only when
the same primary key is represented by `pk_columns`. It preserves primary-key
deferrability and fails closed on the actual introspection keys for defaults,
unique/check/foreign-key constraints, non-primary indexes, partition metadata,
and tablespaces. Planning requires the current `snapshot_contract_version`;
legacy snapshots require recapture. The PostgreSQL introspector reads all
catalogs in one read-only repeatable-read transaction and marks relations with
dropped column slots, which the adapter rejects. Real PostgreSQL round-trip
coverage remains a production gate.

## 7. Structured plan contract

Current `plan_json` contains:

```json
{
  "compiler_version": "pg-erd-forward/v1",
  "postgresql_major": 16,
  "base_digest": "<sha256>",
  "target_digest": "<sha256>",
  "statements": [],
  "proposed_statements": [],
  "blockers": [],
  "risk_summary": {"safe": 0, "warning": 0, "destructive": 0},
  "requires_destructive_confirmation": false,
  "can_dry_run": true,
  "plan_digest": "<sha256>"
}
```

Each current statement contains `kind`, `target`, `object_ref`, rendered `sql`,
`transactional`, `dependencies`, `dependency_refs`, `reversible`, `risk`,
`required_privileges`, and `preconditions`. Risk contains severity, lock mode,
possible rewrite, table scan, data loss, and detail.

`object_ref` and `dependency_refs` are authoritative structured identifiers.
The delimiter-joined `target` and `dependencies` strings are display-only and
must never drive approval, ordering, execution, or audit joins.

When `blockers` is non-empty, `statements` is empty and cannot be executed.
Independent supported deltas are retained in `proposed_statements` solely for
complete review; they are covered by the plan digest and the same risk summary.

Every immutable-plan retrieval recomputes the canonical plan digest and
compares it with both the JSON claim and separately persisted statement digest.
It also verifies the separately persisted compiler, base, and target digests
against their digest-covered JSON values. A mismatch fails closed with
sanitized `409` and returns no plan payload.

Release-v1 requires the following; the plan count/size bound is implemented and
the remaining items are planned:

- explicit segment identity and order;
- postconditions and recovery classification per operation;
- an operation/statement-count and encoded-size bound before persistence
  (**Implemented:** 1,000 executable plus proposed statements and 4 MiB);
- a digest calculation version that covers every execution-relevant field;
- compiler/executor compatibility rejection for unknown versions or kinds;
- a persisted structural diff and complete blocker list;
- enforcement that an expired plan cannot create a run.

Plan SQL is read-only review output. The release executor consumes the
structured stored plan and verifies `plan_digest`; it does not execute a new SQL
string supplied in a run request.

## 8. Migration-plan retrieval and bounded run API

Immutable plan retrieval is **Implemented**. Durable run/event persistence and
the pure state/evidence contract are **Partially implemented**; each route is
classified below without implying worker execution:

| Method and target route | Required request contract | Success | Status |
|---|---|---|---|
| `GET /api/migration-plans/{migration_plan_uuid}` | authenticated member; no body | immutable IDOR-masked plan preview, `200` | **Implemented** |
| `POST /api/migration-plans/{migration_plan_uuid}/dry-runs` | editor+; bounded `Idempotency-Key`; exact `plan_digest` | persisted queued dry-run identity plus identifier-only transactional outbox, `202`; no worker signal | **Implemented** |
| `POST /api/migration-plans/{migration_plan_uuid}/apply-runs` | deployer+; `Idempotency-Key`; exact `plan_digest`; same-plan passed dry-run UUID with exact observed base; exact typed connection name; destructive acknowledgement equal to plan requirement | persisted queued apply intent and hash-chained confirmation evidence, `202`; creates no dispatch or execution authority | **Implemented intent boundary; executor Planned** |
| `GET /api/migration-runs/{migration_run_uuid}` | authenticated member; no body | IDOR-masked bounded state/evidence view; corrupt count/sequence/genesis/transition-graph/cancellation-intent/chronology/evidence/digest-chain/anchor returns sanitized `409` | **Implemented** |
| `POST /api/migration-runs/{migration_run_uuid}/cancel` | editor+; strict positive `expected_state_version` | exact-version cancellation intent, `202`; stable correlated error envelope on rejection | **Implemented** |

Dry-run states:

`queued -> sandbox_running -> live_preflight_running -> passed | drifted | failed`,
with `queued | sandbox_running | live_preflight_running -> cancelled` after a
persisted cancellation intent.

Apply states:

`queued -> applying -> reconciling -> verifying -> verified | drifted_no_apply | not_applied | verification_failed | failed_rolled_back | applied_with_drift | outcome_unknown`,
with only `queued -> cancelled` before apply execution begins.

Terminal semantics are exact:

| State | DDL/outcome claim |
|---|---|
| `passed` | Sandbox execution converged and bounded live read-only preflight passed for an observed digest equal to the integrity-checked plan base; no live DDL ran. The CAS binding and reserved server-authored digest evidence field are Implemented; worker evidence production is Planned. |
| `drifted` / `drifted_no_apply` | Target base mismatch was observed; no plan DDL ran. Dry-run mismatch classification/persistence is Implemented; worker capture and apply-time classification are Planned. |
| `failed` | Dry-run stage failed; no live DDL ran. |
| `cancelled` | A persisted cancellation intent was acknowledged before further execution authority was acquired. Queued cancellation leaves `started_at` unset; no live DDL completion or rollback claim is made. |
| `failed_rolled_back` | Apply started; the transactional segment is proven rolled back. |
| `not_applied` | Reconciliation proves the exact base digest still exists. |
| `verified` | A persisted post-commit verification snapshot equals `target_digest`. |
| `verification_failed` | Commit is known, but verification could not finish; no convergence claim. |
| `applied_with_drift` | Commit is known and verification proves a non-empty residual diff. |
| `outcome_unknown` | Commit/reconciliation evidence is insufficient; replay is forbidden. |

## 9. Authorization, concurrency, and error contract

### Role matrix

| Action | viewer | editor | deployer | owner | Status |
|---|---:|---:|---:|---:|---|
| Read models/plans/evidence | yes | yes | yes | yes | Partially implemented |
| Create/revise a model | no | yes | yes | yes | Implemented |
| Compile a plan | no | yes | yes | yes | Implemented |
| Request a dry-run intent | no | yes | yes | yes | Implemented; worker execution Planned |
| Cancel a non-terminal run | no | yes | yes | yes | Intent and metadata-only worker acknowledgement Implemented; deployed in-flight process cancellation Planned |
| Request live apply | no | no | yes | yes | Implemented as non-dispatched confirmed intent; executor Planned |
| Manage membership | no | no | no | yes | Existing product contract |

The server is authoritative. UI gating never substitutes for authorization.

### Concurrency

- Model create/get/revise responses emit a strong `ETag` containing the current
  revision UUID. Revision requires that exact quoted value in `If-Match`;
  content digests and weak tags are rejected with `409`.
- A missing `If-Match` on the current route is a request-validation error.
- CORS allows request header `If-Match` and exposes response header `ETag`.
- Plan and run requests bind an exact revision and digest; “latest” is not an
  executable identifier.
- Enqueue must compare-and-swap the current model revision, plan digest, passed
  dry-run evidence, and idempotency key in one control-plane transaction.
- A duplicate identical idempotency key returns the original accepted resource;
  reuse with a different effective request returns `409`.
- Once `applying` begins, automatic execution replay is forbidden.

### Error responses

Current implemented endpoints use FastAPI's JSON shape
`{"detail": "<sanitized message>"}`. Current important status codes are:

| Status | Current meaning |
|---:|---|
| `401` | Missing or invalid authentication at the shared auth boundary. |
| `403` | Authenticated project member lacks the required editor/deployer role. |
| `404` | Missing, cross-project, or non-member resource identity on current schema-model/plan/run paths. |
| `409` | Stale model `If-Match` or corrupt durable run history. |
| `413` | Model JSON exceeds 2 MiB, or a compiled plan exceeds 1,000 executable plus proposed statements or 4 MiB. |
| `422` | Request validation, unusable/mismatched/outdated snapshot or connection, invalid model, or snapshot content unsupported by the current adapter. |

Release-v1 read-only endpoint errors remain sanitized and machine-classifiable
using the current string `detail` envelope. Mutating run-action endpoints,
including dry-run creation and cancellation, fix their envelope as
`{"detail":{"code":"...","detail":"...","correlation_id":"..."}}`.
The apply-intent creation route reuses this shape; future executor routes must
also reuse it. Optional bounded
`findings` may be added without exposing source values. The contract distinguishes:

- `stale_revision`, `stale_plan`, `plan_expired`, and `idempotency_conflict`
  (`409`);
- `model_invalid`, `input_binding_invalid`, and `unsupported_schema_feature`
  (`422`);
- `plan_blocked` as a successful preview with `can_dry_run=false`, not an HTTP
  execution failure;
- target operational failure as a durable run state, not a credential-bearing
  synchronous error;
- cross-project missing/unauthorized identity as uniform `404`.

Raw DSNs, SQL batches, row values, and credential-derived text never appear in
errors, logs, events, metrics, or queue payloads.

## 10. Acceptance criteria and traceability

| ID | Release acceptance | Evidence required | Status |
|---|---|---|---|
| FE-AC-001 | Save and reopen an edited canvas as an immutable successor revision. | API + frontend adapter/E2E tests | Partially implemented |
| FE-AC-002 | Every supported change appears in the plan; every unsupported difference blocks without partial statements. | mutation/contract tests across every canonical field | Partially implemented |
| FE-AC-003 | Exact stored plan executes successfully in an isolated compatible PostgreSQL sandbox and reaches `target_digest`. | dedicated ephemeral PostgreSQL 14–18 integration database, separate from metadata and target databases; `test_real_postgres_durable_worker_recovers_without_sandbox_replay` drives the durable handler through test-owned injected capabilities, interrupts the first attempt after committed sandbox convergence, expires its lease, and proves a successor resumes the separately constrained live reader without sandbox replay | Partially implemented core, test-owned worker orchestration, and pre-live-read takeover evidence; deployed provisioning, dependency materialization, isolation/egress proof, credential resolution, cleanup, startup, process/container restart, and worker operation remain Planned |
| FE-AC-004 | Dry run performs no DDL on the live target and returns bounded preflight evidence. | **Partial:** PostgreSQL 14–18 CI runs bounded preflight through a fixture-scoped USAGE/SELECT login with database CREATE/TEMP removed; proves DDL denial and SELECT denial on an ungranted table; forces a real relation-lock wait through the bounded statement timeout; terminates the restricted backend during another lock wait; requires fixed non-secret failures; and verifies reusable transaction cleanup or a closed connection as appropriate. Deployed network/credential isolation and database audit assertions remain Planned. | Partial |
| FE-AC-005 | Live drift before dry run or apply results in no DDL. | injected-drift E2E tests | Planned |
| FE-AC-006 | Apply cannot queue without editor-authored revision, deployer role, exact passed dry run, exact digest, typed target, and destructive acknowledgement when required. | role/tamper/race/API tests | Implemented control-plane boundary; live apply remains Planned |
| FE-AC-007 | Concurrent duplicate submissions create one effective run. | PostgreSQL 14–18 same-key apply race proves the database uniqueness winner persists one apply run and genesis event with no apply dispatch | Partially implemented for the non-dispatched apply intent; live apply concurrency remains Planned |
| FE-AC-008 | Apply-time locks prevent a concurrent write from invalidating data preconditions. | PostgreSQL concurrency integration tests | Planned |
| FE-AC-009 | A statement failure rolls back the complete v1 segment. | fault-injected PostgreSQL test | Planned |
| FE-AC-010 | Commit uncertainty reconciles to `verified`, `not_applied`, or `outcome_unknown` without automatic replay. | crash/fault-injection tests | Planned |
| FE-AC-011 | A successful apply persists a verification snapshot equal to `target_digest`; residual diff is never called verified. | composed-app E2E test | Planned |
| FE-AC-012 | Cross-project identifiers and insufficient roles follow the documented masking/authorization matrix. | IDOR/role test matrix | Partially implemented |
| FE-AC-013 | Browser workflow is keyboard-operable and exposes named risk, progress, error, and terminal-state live regions. | automated accessibility + manual keyboard verification | Planned |
| FE-AC-014 | Backend typing/tests/coverage, frontend typecheck/tests/coverage/build, security scans, and browser E2E pass on the exact release head. | immutable CI check suite | Planned |

## 11. Decision links

- [ADR-0001: Server-authoritative planning](../adr/ADR-0001-server-authoritative-planning.md)
- [ADR-0002: Isolated dry run and live preflight](../adr/ADR-0002-isolated-dry-run-and-preflight.md)
- [ADR-0003: Explicit plan execution segmentation](../adr/ADR-0003-plan-execution-segmentation.md)
- [ADR-0004: Durable runs and recovery](../adr/ADR-0004-durable-runs-and-recovery.md)
- [ADR-0005: Authority, approvals, and convergence](../adr/ADR-0005-authority-approvals-and-convergence.md)
- [Product requirements](../PRD.md)
- [Technical requirements](../TRD.md)
- [Approved design scope](../superpowers/specs/2026-08-09-forward-engineering-design.md)
