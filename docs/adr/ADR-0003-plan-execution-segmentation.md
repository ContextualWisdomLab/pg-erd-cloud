# ADR-0003: Explicit plan execution segmentation

- **Decision status:** Accepted
- **Implementation status:** Partially implemented
- **Date:** 2026-08-09
- **Owners:** pg-erd-cloud maintainers and database operators
- **Supersedes:** none
- **Related:** [ADR-0001](ADR-0001-server-authoritative-planning.md),
  [ADR-0002](ADR-0002-isolated-dry-run-and-preflight.md),
  [ADR-0004](ADR-0004-durable-runs-and-recovery.md),
  [forward-engineering v1 contract](../contracts/forward-engineering-v1.md)

## Context

PostgreSQL DDL differs in lock level, scan/rewrite cost, transaction capability,
required privileges, preconditions, and recovery behavior. In particular,
`CREATE INDEX CONCURRENTLY` cannot run inside a transaction block and a failed
concurrent build can leave an invalid index. Treating all statements as an
undifferentiated SQL batch would make atomicity and recovery claims false.

Compiler v1 currently marks every emitted statement `transactional: true`, but
there is no forward-engineering executor. A release contract is needed before
new operation kinds can reach a target.

## Decision

The stored plan explicitly declares execution segments and recovery boundaries.

For the first production slice:

- exactly one executable segment is allowed;
- every operation in that segment must be transaction-capable;
- the worker executes the ordered segment in one transaction;
- the worker sets bounded `lock_timeout`, `statement_timeout`, and transaction
  timeout policy before work;
- it takes a deterministic target advisory lock, then object locks in sorted
  qualified-name order at compiler-declared modes;
- it rechecks schema and data preconditions on that same connection after locks
  are held;
- any statement or postcondition failure rolls the complete segment back;
- non-transactional operations, including `CREATE INDEX CONCURRENTLY`, are
  blockers and do not coexist with an executable partial plan.

Each operation must carry at least: stable kind, target, ordered SQL,
transaction capability, dependencies, required privileges, declared lock mode,
scan/rewrite/data-loss risk, preconditions, postconditions, and a recovery
classification. The executor dispatches known operation kinds and contract
versions; it does not accept arbitrary text or infer safety from SQL.

Future non-transactional support requires a new compiler contract version and
an ADR that defines segment ordering, resumability, invalid-artifact cleanup,
compensation, verification, and operator intervention. It must not weaken the
single-transaction claim of v1.

## Consequences

### Positive

- Atomicity claims are scoped to an explicit segment.
- Lock acquisition and precondition ordering can be tested deterministically.
- An unsupported operation cannot hide beside executable operations.
- Future online operations have an explicit compatibility and recovery gate.

### Costs and risks

- Ordinary transactional index creation can block writes and must be reported
  as such when index support is introduced.
- Large schema changes may still be operationally unsafe despite transactional
  rollback; risk review and timeouts remain mandatory.
- Plan format changes require compiler/executor version negotiation.
- External writers do not honor pg-erd-cloud advisory locks, so table locks and
  in-transaction precondition checks are still required.

## Alternatives rejected

- **One raw SQL batch with best-effort rollback.** Rejected because transaction
  capability and recovery differ by operation.
- **Automatically split and continue after a non-transactional failure.**
  Rejected because this can leave an unreviewed intermediate schema.
- **Emit `IF EXISTS`/`IF NOT EXISTS` to make retries succeed.** Rejected where
  those clauses would mask drift or a partially applied plan.
- **Retry the entire apply after a worker interruption.** Rejected because the
  commit outcome may be ambiguous.

## Repository evidence

### Implemented

- `app.forward.migration_plan` emits ordered structured statements, each with
  `transactional`, dependency, reversibility, privilege, precondition, and risk
  fields.
- Compiler v1 emits only `transactional: true` statements and suppresses all
  statements when it records a blocker.
- The signed-plan pre-apply manifest emits zero segments for a no-op plan or one
  ordered all-transactional segment for non-empty work. It also maps known
  operations to structured database `CREATE`, schema `CREATE`, or table
  `OWNER` requirements and rejects compiler-v1 privilege-label drift. This is
  target-free input evidence, not privilege observation or execution proof.
- Those exact scopes compile to fixed parameterized PostgreSQL catalog probes.
  The public compiler re-derives the manifest from the exact signed plan and
  expected digest, so a caller-built manifest cannot redirect an otherwise
  valid probe. Compilation neither executes the reads nor binds their results
  to a target, role, transaction, or held lock.
- The pure observation assessor rejects incomplete or positionally mismatched
  privilege/precondition rows and derives only non-authorizing booleans. It
  does not prove target identity, freshness, held locks, or connection binding.

### Planned before production release

- explicit persisted postconditions;
- versioned executor dispatch over stored statement objects;
- deterministic advisory/object locking and apply-time revalidation;
- timeout configuration and classified, redacted failures;
- ephemeral PostgreSQL tests for rollback, concurrency, and lock timeouts.

## Acceptance evidence

Tests must prove that one failing statement rolls back earlier operations, an
unsupported/non-transactional operation prevents all execution, conflicting
writes cannot invalidate locked preconditions, and the executor rejects unknown
operation kinds or compiler versions.
