# Forward Engineering Data Model

- **Document status:** Current physical model plus accepted planned extension
- **Runtime status:** Partially implemented; not production-ready
- **Last reconciled with ORM and Alembic:** 2026-08-11

Repository migrations, ORM definitions, and the Mermaid ERDs below are
authoritative. The
[FigJam companion board](https://www.figma.com/board/MLWimuWoOWhatQ239QihfP)
is non-authoritative and exists to support visual review.

## Status legend

| Label | Meaning |
|---|---|
| **Implemented** | Table and foreign key exist in `backend/app/models.py` and Alembic. |
| **Partially implemented** | Physical storage exists, but a stronger invariant is enforced only by application code or is not yet enforced. |
| **Planned** | Accepted logical entity or relationship; no table or ORM class exists. |
| **Rejected** | Deliberately not stored or not accepted in this boundary. |

## Implemented metadata ERD

The diagram shows the implemented forward-engineering ownership and provenance
slice. It intentionally omits unrelated saved views, annotations, shares, API
keys, revoked tokens, and the generic queue.

```mermaid
erDiagram
  USER_ACCOUNT {
    uuid user_account_uuid PK
    text oidc_subject UK
  }
  PROJECT_SPACE {
    uuid project_space_uuid PK
    uuid created_by_user_uuid FK
    text project_name
  }
  PROJECT_MEMBER {
    uuid project_space_uuid PK, FK
    uuid user_account_uuid PK, FK
    text project_role
  }
  DB_CONNECTION {
    uuid db_connection_uuid PK
    uuid project_space_uuid FK
    text conn_name
    bytes dsn_ciphertext
    bytes dsn_nonce
  }
  SCHEMA_SNAPSHOT {
    uuid schema_snapshot_uuid PK
    uuid project_space_uuid FK
    uuid db_connection_uuid FK
    text status
    text schema_filter
  }
  SCHEMA_SNAPSHOT_DATA {
    uuid schema_snapshot_uuid PK, FK
    jsonb snapshot_json
  }
  SCHEMA_MODEL {
    uuid schema_model_uuid PK
    uuid project_space_uuid FK
    text model_name
    int current_revision_number
    uuid created_by_user_uuid FK
  }
  SCHEMA_MODEL_REVISION {
    uuid schema_model_revision_uuid PK
    uuid schema_model_uuid FK
    int revision_number
    text revision_digest
    jsonb model_json
    uuid base_schema_snapshot_uuid FK
    uuid created_by_user_uuid FK
  }
  MIGRATION_PLAN {
    uuid migration_plan_uuid PK
    uuid project_space_uuid FK
    uuid schema_model_revision_uuid FK
    uuid db_connection_uuid FK
    uuid base_schema_snapshot_uuid FK
    text compiler_version
    text base_digest
    text target_digest
    text statement_digest
    jsonb plan_json
    uuid created_by_user_uuid FK
    timestamptz expires_at
  }
  MIGRATION_RUN {
    uuid migration_run_uuid PK
    uuid project_space_uuid FK
    uuid migration_plan_uuid FK
    uuid passed_dry_run_uuid FK
    text run_kind
    text state
    int state_version
    text idempotency_key_hash
    text plan_digest
    text request_digest
    text confirmation_digest
    boolean destructive_confirmation
    text latest_event_digest
    uuid requested_by_user_uuid FK
    boolean cancellation_requested
    text observed_base_digest
    jsonb evidence_json
    text error_code
    timestamptz created_at
    timestamptz updated_at
    timestamptz started_at
    timestamptz finished_at
  }
  MIGRATION_RUN_DISPATCH {
    uuid migration_run_dispatch_uuid PK
    uuid migration_run_uuid FK, UK
    text dispatch_kind
    text status
    int attempt_count
    timestamptz not_before
    timestamptz created_at
    timestamptz published_at
  }
  MIGRATION_RUN_ATTEMPT {
    uuid migration_run_attempt_uuid PK
    uuid migration_run_uuid FK
    int attempt_number UK
    int acquired_state_version
    text status
    text worker_identity_hash
    text signal_lease_token_hash
    timestamptz lease_expires_at
    timestamptz acquired_at
    timestamptz last_heartbeat_at
    timestamptz finished_at
  }
  MIGRATION_RUN_EVENT {
    uuid migration_run_event_uuid PK
    uuid migration_run_uuid FK
    int sequence_number
    text event_type
    text state_before
    text state_after
    jsonb evidence_json
    text previous_event_digest
    text event_digest
    uuid actor_user_uuid FK
    timestamptz created_at
  }

  USER_ACCOUNT ||--o{ PROJECT_SPACE : creates
  USER_ACCOUNT ||--o{ PROJECT_MEMBER : holds
  PROJECT_SPACE ||--o{ PROJECT_MEMBER : authorizes
  PROJECT_SPACE ||--o{ DB_CONNECTION : owns
  DB_CONNECTION ||--o{ SCHEMA_SNAPSHOT : captures
  PROJECT_SPACE ||--o{ SCHEMA_SNAPSHOT : scopes
  SCHEMA_SNAPSHOT ||--o| SCHEMA_SNAPSHOT_DATA : has
  PROJECT_SPACE ||--o{ SCHEMA_MODEL : owns
  USER_ACCOUNT ||--o{ SCHEMA_MODEL : creates
  SCHEMA_MODEL ||--o{ SCHEMA_MODEL_REVISION : versions
  SCHEMA_SNAPSHOT o|--o{ SCHEMA_MODEL_REVISION : bases
  USER_ACCOUNT ||--o{ SCHEMA_MODEL_REVISION : creates
  PROJECT_SPACE ||--o{ MIGRATION_PLAN : scopes
  SCHEMA_MODEL_REVISION ||--o{ MIGRATION_PLAN : compiles_to
  DB_CONNECTION ||--o{ MIGRATION_PLAN : targets
  SCHEMA_SNAPSHOT ||--o{ MIGRATION_PLAN : starts_from
  USER_ACCOUNT ||--o{ MIGRATION_PLAN : creates
  PROJECT_SPACE ||--o{ MIGRATION_RUN : scopes
  MIGRATION_PLAN ||--o{ MIGRATION_RUN : attempts
  USER_ACCOUNT ||--o{ MIGRATION_RUN : requests
  MIGRATION_RUN ||--o{ MIGRATION_RUN_ATTEMPT : owns
  MIGRATION_RUN ||--o| MIGRATION_RUN_DISPATCH : dispatches
  MIGRATION_RUN ||--o{ MIGRATION_RUN_EVENT : records
  USER_ACCOUNT o|--o{ MIGRATION_RUN_EVENT : acts
```

### Implemented key and deletion semantics

| Child foreign key | Parent | Nullable | On parent delete | Implemented cardinality |
|---|---|---:|---|---|
| `project_member.project_space_uuid` | `project_space` | no | `CASCADE` | Each membership has exactly one project; a project has zero or more memberships at the database boundary. |
| `project_member.user_account_uuid` | `user_account` | no | `CASCADE` | Each membership has exactly one user; a user has zero or more memberships. |
| `db_connection.project_space_uuid` | `project_space` | no | `CASCADE` | Each connection belongs to one project; a project has zero or more connections. |
| `schema_snapshot.project_space_uuid` | `project_space` | no | `CASCADE` | Each snapshot is scoped to one project; a project has zero or more snapshots. |
| `schema_snapshot.db_connection_uuid` | `db_connection` | no | `CASCADE` | Each snapshot came from one connection; a connection has zero or more snapshots. |
| `schema_snapshot_data.schema_snapshot_uuid` | `schema_snapshot` | no; also PK | `CASCADE` | A snapshot has zero or one data row; each data row belongs to exactly one snapshot. |
| `schema_model.project_space_uuid` | `project_space` | no | `CASCADE` | Each model belongs to one project; a project has zero or more models. |
| `schema_model_revision.schema_model_uuid` | `schema_model` | no | `CASCADE` | Each revision belongs to one model; a model has zero or more revisions physically. Current APIs create the model with revision 1 atomically. |
| `schema_model_revision.base_schema_snapshot_uuid` | `schema_snapshot` | yes | `RESTRICT` | A revision has zero or one base snapshot; a snapshot can base zero or more revisions. |
| `migration_plan.project_space_uuid` | `project_space` | no | `CASCADE` | Each plan is scoped to one project; a project has zero or more plans. |
| `migration_plan.schema_model_revision_uuid` | `schema_model_revision` | no | `RESTRICT` | Each plan compiles one revision; a revision can produce zero or more plans. |
| `migration_plan.db_connection_uuid` | `db_connection` | no | `RESTRICT` | Each plan targets one connection; a connection can have zero or more plans. |
| `migration_plan.base_schema_snapshot_uuid` | `schema_snapshot` | no | `RESTRICT` | Each plan binds one base snapshot; a snapshot can base zero or more plans. |
| `migration_run.project_space_uuid` | `project_space` | no | `CASCADE` | Each durable run is scoped to one project; a project has zero or more runs. |
| `migration_run.migration_plan_uuid` | `migration_plan` | no | `RESTRICT` | Each durable run attempts one immutable plan; plan deletion is blocked while evidence remains. |
| `migration_run.passed_dry_run_uuid` | `migration_run` | nullable for dry runs; required for apply | `RESTRICT` | Each apply intent names one exact dry run; the writer additionally requires same project, plan, digest, passed state, no cancellation, and exact observed base. |
| `migration_run.requested_by_user_uuid` | `user_account` | no | `NO ACTION` | Each run records one requesting actor. |
| `migration_run_dispatch.migration_run_uuid` | `migration_run` | no; unique | `CASCADE` | The implemented writer adds one identifier-only dispatch intent for each new dry run; the database permits zero or one dispatch row per run. |
| `migration_run_attempt.migration_run_uuid` | `migration_run` | no | `CASCADE` | A run has numbered attempt history and at most one partial-indexed active owner. |
| `migration_run_event.migration_run_uuid` | `migration_run` | no | `CASCADE` | Each event belongs to one run; approved run deletion removes its event sequence atomically. |
| `migration_run_event.actor_user_uuid` | `user_account` | yes | `NO ACTION` | Worker events may be system-authored; human actions retain an actor. |

All `created_by_user_uuid` columns shown are non-null foreign keys to
`user_account` with the database default delete behavior (`NO ACTION`).

### Physical invariants and application invariants

| Invariant | Enforcement | Status |
|---|---|---|
| Model name is unique inside a project. | Database unique constraint on `(project_space_uuid, model_name)`. | Implemented |
| Revision number is unique inside a model. | Database unique constraint on `(schema_model_uuid, revision_number)`. | Implemented |
| A model revision is immutable. | No update route; application convention. There is no database trigger preventing update. | Partially implemented |
| `current_revision_number` names an existing revision of the same model. | Current API transaction and row lock. No physical FK can express the composite pointer as modeled. | Partially implemented |
| Plan project, revision project, connection project, and snapshot project match; the snapshot came from that exact connection and succeeded. | `app.api.migration_plans.create_migration_plan` before insert. | Implemented in the API; not a database constraint |
| Plan SQL and execution fields cannot change. | No current update route. There is no database immutability trigger. | Partially implemented |
| Expired plans cannot start a run. | The public dry-run intent route delegates to the writer that verifies expiry before its conflict-winner insert; worker execution remains absent. | Partially implemented |
| A new run and genesis event are atomic; only dry runs receive a dispatch. | `create_migration_run` adds the run/event and, for dry runs only, one unique dispatch to the caller-owned transaction. Confirmed apply intents deliberately receive no dispatch. | Implemented |
| An apply intent cannot become executable by creation. | The API locks the schema-model row `FOR UPDATE`; the writer validates current exact revision UUID/number/digest plus plan/connection/passed-run/base/destructive bindings, persists a confirmation digest and genesis evidence, and creates no dispatch. Database checks require confirmation fields only for apply rows. | Implemented intent boundary; executor Planned |
| Dispatch and attempt storage carry no execution material. | Dispatch contains identifiers/timestamps only. Attempts contain numbered ownership timestamps plus SHA-256 worker/signal-token hashes—never raw identity, DSN, SQL, plan, or credential. Exact unexpired-owner acquire/renew/finish and expiry takeover are implemented. | Implemented persistence/signal/attempt boundary; application wiring, credential binding, and execution Planned |
| Secrets or raw SQL never appear in run evidence. | `canonicalize_run_evidence` recursively rejects SQL, DSN, password, secret, token, and credential field tokens and bounds depth, items, strings, and total JSON bytes. | Implemented at the evidence-construction boundary; all writers must use it |
| Duplicate run requests select one durable identity. | Unique `(project_space_uuid, run_kind, idempotency_key_hash)` plus separately persisted `request_digest`; public dry-run/apply-intent routes delegate to the PostgreSQL conflict-winner writer, which reuses only the same effective request and rejects different reuse. | Implemented for dry-run and non-dispatched apply intent; workers Planned |
| Run/event state tokens, sequence numbers, digest links, and attempt ownership are valid. | Database checks constrain run/event state and SHA-256 shapes; exact transition/result CAS writers preserve plan/evidence identity. Attempt acquisition serializes on the run, one partial unique index permits at most one active owner, history numbering is unique, renewal requires an executable uncancelled run, and renew/finish require the exact unexpired hashed owner. | Implemented persistence/polling/result bridges and durable attempt primitives; consumer/credential/execution binding Planned |

The existing result boundaries remain explicit: `complete_isolated_dry_run`
revalidates sandbox evidence and derives the fixed next CAS;
`execute_bound_live_preflight` binds fresh capture and checks to one read-only
repeatable-read transaction; `complete_live_preflight` validates that exact
result and derives the only terminal classification. Durable attempt ownership
does not replace or grant authority to any of these boundaries.

`migration_plan.statement_digest` stores the compiler's current `plan_digest`.
It is provenance, not a database idempotency key: the same logical SQL may be
planned for different targets or recreated after expiry.

`migration_plan` is a derived review artifact with a 24-hour execution lifetime.
Creation-time maintenance may delete it only after a further 30-day retention
window, only within the authorized project, and only when no `migration_run`
references it. Any plan with durable run evidence is retained by policy and by
the restrictive foreign key.

`migration_plan.plan_json` separates executable `statements` from
`proposed_statements`. When any blocker exists, `statements` is empty and
`proposed_statements` retains independently supported deltas as review-only
evidence. `risk_summary` and `requires_destructive_confirmation` are computed
over all proposals, so a blocked plan can still disclose destructive risk. A
future executor must reject blocked plans and must never promote proposals to
execution input.

## Physical run foundation — Implemented

`migration_run`, `migration_run_dispatch`, `migration_run_event`, and
`migration_run_attempt` now exist in the ORM and Alembic revisions
`0010_migration_run`, `0011_migration_run_attempt`,
`0012_apply_intent_confirmation`, and
`0012_apply_intent_confirmation` with the fields
shown in the implemented ERD
above. Passed-dry-run, confirmation-digest, and destructive-confirmation
bindings are physical and Implemented. The logical diagram below retains the
verification-snapshot reference as a **Planned extension**; that field does not
exist physically and must not be inferred from the implemented tables.

```mermaid
erDiagram
  PROJECT_SPACE ||--o{ MIGRATION_RUN : scopes
  USER_ACCOUNT ||--o{ MIGRATION_RUN : requests
  MIGRATION_PLAN ||--o{ MIGRATION_RUN : attempts
  MIGRATION_RUN o|--o{ MIGRATION_RUN : proves_apply
  SCHEMA_SNAPSHOT o|--o{ MIGRATION_RUN : verifies
  MIGRATION_RUN ||--o{ MIGRATION_RUN_EVENT : records
  MIGRATION_RUN ||--o| MIGRATION_RUN_DISPATCH : dispatches
  MIGRATION_RUN ||--o{ MIGRATION_RUN_ATTEMPT : owns
  USER_ACCOUNT o|--o{ MIGRATION_RUN_EVENT : acts

  MIGRATION_RUN {
    uuid migration_run_uuid PK
    uuid project_space_uuid FK
    uuid migration_plan_uuid FK
    uuid requested_by_user_uuid FK
    uuid passed_dry_run_uuid FK
    uuid verification_snapshot_uuid FK
    text run_kind
    text bound_plan_digest
    text idempotency_key
    text request_digest
    text confirmation_digest
    boolean destructive_confirmation
    text state
    int state_version
    text observed_base_digest
    jsonb evidence_json
    text error_code
    timestamptz created_at
    timestamptz started_at
    timestamptz finished_at
  }
  MIGRATION_RUN_EVENT {
    uuid migration_run_event_uuid PK
    uuid migration_run_uuid FK
    uuid actor_user_uuid FK
    int event_sequence
    text event_kind
    text from_state
    text to_state
    jsonb evidence_json
    timestamptz created_at
  }
  MIGRATION_RUN_DISPATCH {
    uuid migration_run_dispatch_uuid PK
    uuid migration_run_uuid FK
    text dispatch_kind
    text status
    int attempt_count
    timestamptz not_before
    timestamptz created_at
    timestamptz published_at
  }
  MIGRATION_RUN_ATTEMPT {
    uuid migration_run_attempt_uuid PK
    uuid migration_run_uuid FK
    int attempt_number
    int acquired_state_version
    text status
    text worker_identity_hash
    text signal_lease_token_hash
    timestamptz lease_expires_at
    timestamptz acquired_at
    timestamptz last_heartbeat_at
    timestamptz finished_at
  }
```

Target foreign-key and cardinality rules follow. The implemented foreign-key
table above is authoritative for current deletion behavior; this table marks
the implemented passed-dry-run relationship and the remaining planned field.

| Child foreign key | Parent | Nullable / conditional rule | Target deletion and cardinality |
|---|---|---|---|
| `migration_run.migration_plan_uuid` | `migration_plan` | non-null | `RESTRICT`; every run attempts one immutable plan, and a plan has zero or more dry-run/apply attempts. |
| `migration_run.passed_dry_run_uuid` | `migration_run` | null for dry runs; required for apply and must reference a `passed` run for the same plan/digest/base | **Implemented:** `RESTRICT`; one passed dry run can prove zero or more non-dispatched apply intents while its exact plan remains unexpired. |
| `migration_run.verification_snapshot_uuid` | `schema_snapshot` | null until verification; required for `verified` | `RESTRICT`; a run has zero or one verification snapshot, and a snapshot can be referenced by zero or more runs physically. The service must create a dedicated snapshot per apply run. |

Additional **Implemented and Planned** invariants:

- **Implemented — scheduled relay lifecycle:** an explicit opt-in
  application task. Each bounded publisher attempt runs in its own
  caller-owned transaction; failure rolls back and empty/failure iterations
  wait at a positive configured interval.
- **Implemented — execution-neutral queue consumer contract:** an injected
  handler receives the exact signal claim (run UUID plus opaque lease-token)
  and must complete before exact-lease acknowledgement; sanitized failure
  releases only that lease at a bounded retry time. The ready payload remains
  UUID-only. The contract never loads a plan, credential, SQL batch, or target
  value.
- **Implemented — consumer-to-attempt binding:** the dual-lease adapter commits
  exact attempt acquisition before invoking an injected handler, renews in
  fresh metadata transactions, cancels on ownership loss, and records exact
  completion before the signal may be acknowledged. It accepts no execution
  material or credentials.
- **Planned — application startup wiring and worker execution:** no startup
  task consumes migration signals or executes target SQL.
- One database uniqueness rule plus `request_digest` implements idempotency:
  identical reuse returns the original run, while different effective input
  returns `409`.
- State changes compare-and-swap `state_version`; events are append-only and
  ordered uniquely by `(migration_run_uuid, event_sequence)`.
- Project, plan, dry-run evidence, target connection, and verification
  snapshot tenancy must agree. Conditional state invariants require service
  transactions and database constraints where PostgreSQL can express them.
- Event/evidence JSON contains bounded identifiers, digests, counts, durations,
  and sanitized diagnostics only. DSNs, decrypted secrets, SQL batches, and
  sampled row values are **Rejected**.

## Related authority

- [Forward-engineering v1 contract](contracts/forward-engineering-v1.md)
- [UML and state machines](UML.md)
- [ADR-0004: durable runs and recovery](adr/ADR-0004-durable-runs-and-recovery.md)
- [Threat model](security/forward-engineering-threat-model.md)
- [Operational runbook](runbooks/forward-engineering.md)
