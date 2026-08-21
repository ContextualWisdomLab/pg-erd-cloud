# ADR-0004: Server-Authoritative Forward Engineering

- Status: Accepted
- Lifecycle: `planned`
- Date: 2026-08-09
- Supersedes: `/api/connections/{id}/apply-sql` as the target architecture

## Context

The browser can currently render quoted identifiers, foreign keys, comments,
and concurrent indexes, while the backend compatibility endpoint accepts only
a conservative subset of unquoted client-authored SQL. It executes accepted
text synchronously in one target transaction. That creates two inconsistent
compilers and provides no immutable desired-model revision, target fingerprint,
plan digest, bound approval, durable execution, non-transactional recovery, or
semantic convergence evidence.

PostgreSQL DDL has statement-specific lock, rewrite, privilege, transaction,
and recovery behavior. `CREATE INDEX CONCURRENTLY`, for example, cannot be
modeled as an ordinary statement inside one all-or-nothing transaction.

## Decision

The server owns a single typed schema model and structured migration plan used
by diff, rendering, validation, dry-run, apply, audit, and convergence. The
workflow is:

1. persist an immutable desired-model revision;
2. fingerprint the observed target and compile an ordered statement graph;
3. fail closed on unsupported or ambiguous constructs;
4. run destructive execution only in an isolated compatible environment and
   perform bounded read-only preflight against the real target;
5. bind approval to the exact plan digest, model revision, target identity,
   target fingerprint, policy result, actor, and expiry;
6. revalidate drift and privileges, serialize per target, and execute through a
   durable idempotent job with explicit transactional segments;
7. re-introspect and compare semantics before reporting convergence.

The legacy text endpoint is `deprecated`; it does not gain broader SQL support
and is removed only through a separately reviewed compatibility migration.

## Alternatives considered

- Expand the string allowlist: rejected because textual scanning is not a
  complete SQL parser, dependency planner, risk model, or approval binding.
- Trust browser-generated SQL: rejected because clients are mutable and cannot
  be the execution authority.
- Transaction and rollback as dry-run: rejected because it does not model
  target locks, large-table behavior, external effects, or non-transactional
  statements safely.
- Generate a script for a human to run: retained as an export option, but it
  cannot satisfy in-product apply, recovery, audit, or convergence outcomes.

## Consequences

- Forward Engineering requires new persistence entities and API contracts;
  these remain `planned` until migrations, code, tests, and operations exist.
- Capability support is PostgreSQL-version-specific and explicit. Unsupported
  constructs remain visible and block apply instead of being silently lost.
- Non-transactional partial completion is a first-class recoverable state, not
  mislabeled as rolled back.
- The UI may edit locally, but execution always resolves a stored immutable
  revision and server-produced plan.

## Verification

- Property and integration tests prove deterministic normalization, ordering,
  digest stability, capability classification, real PostgreSQL execution, and
  semantic round-trip equivalence.
- Failure injection covers drift, duplicate submission, process loss, target
  timeout, cancellation, privilege loss, and partial non-transactional work.
- Browser E2E proves the exact plan reviewed is the plan authorized and run.

## References

See PostgreSQL Global Development Group (2026), Curino et al. (2013), Rae et
al. (2013), and Hu et al. (2023) in
[`docs/references.md`](../references.md).
