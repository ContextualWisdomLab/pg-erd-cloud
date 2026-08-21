# ADR-0001: Server-authoritative planning

- **Decision status:** Accepted
- **Implementation status:** Partially implemented
- **Date:** 2026-08-09
- **Owners:** pg-erd-cloud maintainers
- **Supersedes:** none
- **Related:** [ADR-0002](ADR-0002-isolated-dry-run-and-preflight.md),
  [ADR-0003](ADR-0003-plan-execution-segmentation.md),
  [forward-engineering v1 contract](../contracts/forward-engineering-v1.md)

## Context

The existing product has three contracts that cannot safely be connected as a
production workflow:

1. the React canvas is an editing view, not an execution authority;
2. export and snapshot-diff code can render SQL that the legacy
   `POST /api/connections/{db_connection_uuid}/apply-sql` validator rejects;
3. the legacy endpoint accepts browser-supplied SQL and has no immutable link
   between what a person reviewed and what a worker executes.

A plan must also explain unsupported semantics. Omitting a desired change while
claiming that the target digest is reachable would be a false safety signal.

## Decision

The server owns the complete desired-model-to-plan boundary.

- The browser submits semantic schema intent as model JSON, never executable
  SQL, for the graphical workflow.
- `app.forward.schema_model.canonicalize_schema_model` validates and
  canonicalizes that untrusted intent. A SHA-256 revision digest identifies the
  exact canonical content.
- `schema_model_revision` rows are append-only through the API. Saving a
  successor uses `If-Match` against the strong revision-UUID `ETag`; the model
  content digest alone is not a concurrency token because the base snapshot
  may change independently.
- `app.forward.migration_plan.compile_migration_plan` compiles one exact model
  revision against one exact succeeded snapshot and connection. The resulting
  `migration_plan` is immutable through the API and binds compiler version,
  base digest, target digest, structured statements, risks, blockers, actor,
  target, and expiry.
- One structured statement/operation representation is authoritative for SQL
  rendering, dependencies, privileges, transaction capability, preconditions,
  risk, execution, and audit. An executor must consume the stored plan and
  expected digest; it must not re-parse browser SQL to recover intent or risk.
- `object_ref` and `dependency_refs` are the identifier authority. Dot/colon
  joined `target` and `dependencies` strings are display-only because quoted
  PostgreSQL identifiers may contain those delimiters.
- Every semantic difference must produce either an executable operation or a
  blocker. A plan containing a blocker has no executable statements and cannot
  enter dry run.
- The graphical workflow will execute by plan UUID plus digest. It will not use
  or broaden `apply-sql`. The legacy endpoint remains a transitional,
  separately authorized compatibility surface.

Repository Markdown and Mermaid diagrams are authoritative. The
[FigJam board](https://www.figma.com/board/MLWimuWoOWhatQ239QihfP) is a
non-authoritative visual companion.

## Consequences

### Positive

- Review, approval, dry-run evidence, execution, and verification can be bound
  to one immutable hash.
- PostgreSQL identifier quoting and compiler support are enforced once on the
  server.
- A narrow compiler can fail closed without granting the browser SQL authority.
- Auditors can trace a live action back to an actor, model revision, base
  snapshot, compiler version, and target.

### Costs and risks

- The backend needs a versioned canonical model contract and migrations for
  every compatible format change.
- The frontend needs explicit graph/model adapters; React Flow node IDs and
  labels cannot act as database identities.
- Canonical fields that affect the target digest but do not yet compile are
  rejected or surfaced as blockers. Compiler v1 now blocks schema removal,
  table/column comment changes, and non-append column ordering rather than
  advertising false convergence.
- A blocked plan exposes no executable statements. Independent supported
  deltas remain digest-bound in `proposed_statements` for review, so one
  unsupported change does not hide other risk-bearing work.
- Type aliases normalize to PostgreSQL catalog spelling; serial pseudo-types
  are rejected, and admitted type changes are conservatively classified as
  destructive until a proven widening matrix exists.
- The snapshot adapter admits only the proven subset. It filters verified
  primary-key backing indexes, preserves primary-key deferrability, and returns
  a sanitized `422` for unsupported defaults, non-primary indexes,
  unique/check/foreign-key constraints, partition metadata, or tablespaces.

## Alternatives rejected

- **Connect canvas/export SQL directly to `apply-sql`.** Rejected because the
  generator and validator support different grammars and the browser would
  control executable text.
- **Broaden a SQL allow/deny-list parser.** Rejected because parsing text after
  the fact cannot reliably reconstruct schema intent, dependencies, provenance,
  or risk across PostgreSQL grammar versions.
- **Let the browser classify risk while the server only executes.** Rejected
  because review and enforcement could disagree.
- **Silently skip unsupported objects.** Rejected because a successful result
  would not mean the desired model converged.

## Repository evidence

### Implemented

- `app.forward.schema_model` canonicalization and revision digests.
- `SchemaModel`, `SchemaModelRevision`, and `MigrationPlan` persistence models
  plus Alembic revisions `0008_schema_model_revision` and
  `0009_migration_plan`.
- Current model routes under `/api/schema-models` and current plan creation at
  `POST /api/schema-model-revisions/{schema_model_revision_uuid}/migration-plans`.
- `app.forward.migration_plan` structured compiler with deterministic plan
  digest, risk summary, and blocker suppression.

### Planned before production release

- plan retrieval, dry-run, apply-run, and run polling APIs;
- a structured executor that consumes only persisted plans;
- extension of the deliberately narrow fail-closed subset without semantic
  loss;
- frontend model adapters and review workflow;
- integration evidence that the stored statement plan executes and converges.

## Acceptance evidence

This decision is implemented only when contract tests prove that every admitted
model difference becomes an operation or blocker, no graphical-workflow request
contains executable SQL, and the exact persisted plan digest is the value used
by dry run, approval, execution, and verification.
