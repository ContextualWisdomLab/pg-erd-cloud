# ADR-0005: Least authority, explicit approval, and verified convergence

- **Decision status:** Accepted
- **Implementation status:** Partially implemented
- **Date:** 2026-08-09
- **Owners:** pg-erd-cloud maintainers, security owners, and operators
- **Supersedes:** none
- **Related:** [ADR-0001](ADR-0001-server-authoritative-planning.md),
  [ADR-0004](ADR-0004-durable-runs-and-recovery.md),
  [forward-engineering v1 contract](../contracts/forward-engineering-v1.md)

## Context

Editing a desired model, proving a plan, authorizing production DDL, holding a
target credential, and declaring convergence are different authorities. A UI
button is not authorization, and a successful commit acknowledgement is not
proof that the live schema equals the desired model. Destructive operations
need stronger evidence of informed intent than a generic confirmation.

The repository already encrypts DSNs and has project roles. The current role
ordering is `viewer < editor < deployer < owner`, and live
`apply-sql` (`dry_run=false`) now requires `deployer`. The complete immutable
plan approval and convergence flow is not implemented.

## Decision

### Authorization and credential boundaries

- `viewer` can inspect project-scoped models, plans, and bounded evidence.
- `editor` can create/revise models, compile plans, and request dry runs.
- `deployer` can request live apply after every plan and evidence gate passes.
- `owner` manages membership and inherits deployer authority.
- Every API performs server-side project membership and role checks; frontend
  control visibility is explanatory only.
- Reads and mutations mask cross-project identifiers using the repository's
  uniform not-found behavior. No response reveals another project's resource.
- Target DSNs remain encrypted at rest, are decrypted only in the guarded
  connection boundary, and never enter browser, queue, event, or plan payloads.
- Sandbox credentials and live-target credentials are different authorities.

### Approval binding

An apply request must bind the unexpired plan UUID and digest, the exact passed
dry-run UUID for the same plan/base observation, a unique idempotency key, and
the current model revision. The deployer types the exact connection name. If
the plan contains destructive operations, a separate acknowledgement is
required. The server stores only a normalized confirmation/approval record and
hash; it does not treat client-rendered warning text as authority.

Any changed revision, checksum, target fingerprint, expired plan, missing dry
run, insufficient role, or missing confirmation prevents queueing. Enqueue and
model revision supersession use one compare-and-swap decision: either the stale
request returns `409`, or the accepted run remains frozen to the exact plan.

### Convergence

Commit success is followed by reverse engineering through the normal snapshot
boundary. The worker persists a dedicated verification snapshot and compares
its canonical digest with the desired target digest. Only equality produces
`verified`. A known commit with residual differences produces
`applied_with_drift`; unavailable verification produces `verification_failed`
or `outcome_unknown` according to the recovery evidence. The UI must never
describe these states as unchanged or verified.

### Governance responsibility

Central automation/governance owns reusable policy gates, required evidence,
security baselines, and cross-repository reporting. pg-erd-cloud owns the leaf
product contract, compiler/executor correctness, PostgreSQL-specific risk,
runtime authorization, target safety, user experience, tests, and operational
acceptance. A central green signal cannot replace leaf convergence evidence.

## Consequences

### Positive

- Production mutation requires a distinct capability and evidence-bound human
  intent.
- Destructive approval cannot be reused for a changed plan.
- Credential exposure is minimized across browser, queue, sandbox, and audit
  boundaries.
- Success means observed convergence, not merely an API or commit response.

### Costs and risks

- Projects need a deployer role migration and clear owner/deployer UX.
- Typed confirmation adds deliberate friction.
- Re-introspection adds time after commit and can fail independently.
- Uniform IDOR masking must be corrected consistently; current model creation,
  revision, and plan-creation paths do not all mask non-members identically.

## Alternatives rejected

- **Let every editor apply.** Rejected because authoring and production
  deployment are distinct capabilities.
- **Rely on a disabled UI button.** Rejected because clients are untrusted.
- **Approve “the latest plan.”** Rejected because the approved content can race
  with a model edit or target drift.
- **One generic confirmation for destructive plans.** Rejected because data-loss
  intent must be explicit and separately recorded.
- **Treat commit acknowledgement as success.** Rejected because convergence has
  not been observed.

## Repository evidence

### Implemented

- `app.permissions._ROLE_RANK` includes `deployer` between `editor` and `owner`.
- Legacy live `apply-sql` requires `deployer`; its rollback-only compatibility
  mode requires `editor`.
- Connection DSNs are encrypted at rest and guarded target-connection code is
  reused for database access.
- Plans bind actor, project, connection, base snapshot, model revision, digests,
  compiler version, and expiry.

### Planned before production release

- evidence-bound apply-run request and compare-and-swap enqueue;
- typed connection-name and destructive acknowledgements;
- uniform IDOR masking across every new resource;
- verification snapshots, convergence comparison, residual diffs, and UI;
- audit events, privilege tests, secret-boundary tests, and leaf operational
  acceptance evidence.

## Acceptance evidence

Authorization tests must cover every role and cross-project identifier. Race
tests must prove stale revisions and fingerprints execute no DDL. End-to-end
tests must show that the only successful terminal result is a persisted
verification snapshot whose canonical digest equals the approved target digest.
