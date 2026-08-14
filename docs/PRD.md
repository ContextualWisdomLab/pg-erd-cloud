# Product Requirements: Safe Forward Engineering

## Document control

- **Product:** pg-erd-cloud
- **Status:** Approved product direction; Phase 1 control plane partially implemented
- **Date:** 2026-08-09
- **Authoritative scope:** This PRD defines outcomes and release gates. The
  [TRD](TRD.md), [v1 contract](contracts/forward-engineering-v1.md), and
  [ADRs](adr/README.md) define technical behavior.
- **Visual companion:** [Figma FigJam board](https://www.figma.com/board/MLWimuWoOWhatQ239QihfP).
  Repository Markdown and Mermaid remain authoritative.

## Product outcome

Data architects can turn a reverse-engineered PostgreSQL schema into a reviewed
desired model, prove the exact immutable migration plan outside production,
authorize it with least privilege, and receive durable evidence that the live
schema converged. A missing proof, unsupported construct, stale target, or
uncertain outcome must stop the workflow or be reported honestly; it must never
be converted into apparent success.

The current repository implements the control-plane foundation plus partial
validation/recovery primitives: canonical model revisions, immutable plans,
fail-closed subset handling, a `deployer` role, isolated execution and bounded
preflight cores, durable run/event/outbox identity, and hashed lease-bound
worker-attempt ownership. Consumer-to-attempt binding is **Implemented** as an
execution-neutral dual-lease adapter. Application startup wiring, credentials,
sandbox lifecycle, worker execution, durable apply, post-apply convergence,
and the frontend workflow are **Planned** release blockers. Typed browser
transport is **Partially implemented** for the current plan/run endpoints and
accepts only identifiers, digests, typed confirmation, and optimistic state
versions. The plan review panel is **Partially implemented** as an accessible,
read-only view of provenance, risk, blockers, executable statements, and
review-only proposals. Fixed loading/error/retry behavior and stale-response
suppression is **Partially implemented** for exact plan retrieval; Forward UI
remains **Planned**. The Forward Engineering modal shell is **Partially
implemented** as a dedicated accessible container. The dry-run intent control
is **Partially implemented**: it follows the server's `can_dry_run` and blocker
decision, submits only the exact plan identity/digest, prevents concurrent
submits, and retains one bounded idempotency key across an ambiguous retry.
Within an open modal, an accepted dry run replaces any supplied audit run so
only one status/polling surface remains active. Closing and reopening restores
the caller-supplied run instead of reusing that modal-session override.
The apply intent control is **Partially implemented**: only an exact passed
dry-run for the reviewed plan/digest/base enables a deployer confirmation form;
the operator must type the exact target connection name and acknowledge any
destructive plan, and ambiguous retries preserve both one idempotency key and
the first submitted confirmation. The accepted result is a non-dispatched
intent, not live DDL authority. Graph/model adapters, apply execution controls,
and broader orchestration remain absent.
The run status and audit
panel is **Partially implemented** as an optional read-only exact-run view. It
announces the bounded state meaning, pending cancellation intent, terminal
`cancelled` acknowledgement, and sanitized error
code, and renders hash-chain event metadata without exposing generic evidence
payloads. Sequential terminal-aware polling is **Partially implemented**: a
new request is scheduled only after the preceding response and stops at the
first terminal state. The cancellation intent control is **Partially
implemented**: it appears only before a terminal state and before a recorded
intent, submits the exact current state version once, refreshes after acceptance,
and never replays an ambiguous write automatically. The durable dry-run
consumer now persists terminal cancellation acknowledgement and settles
already-terminal redelivery without replay. Apply/recovery controls and
browser E2E remain absent; deployed in-flight process cancellation is Planned.

## Actors and authority

| Actor | Job | Maximum forward authority |
|---|---|---|
| Viewer | Inspect models, plans, risks, and evidence | Read |
| Editor | Save desired revisions and request plans/dry runs | No production DDL |
| Deployer | Authorize a reviewed exact plan for one target | Live apply |
| Owner | Manage membership and deployment authority | Deployer + administration |
| Operator/auditor | Diagnose durable states and preserve evidence | No implicit product role |

The API is authoritative. Hiding or disabling a UI control never substitutes
for server authorization.

## Required user journey

1. Select a succeeded snapshot from the intended connection.
2. Edit the desired schema and save an immutable successor revision under
   optimistic concurrency.
3. Review the exact semantic diff, ordered SQL, dependencies, privileges,
   blockers, reversibility, and lock/scan/rewrite/data-loss risks.
4. Execute the exact plan in an isolated compatible PostgreSQL sandbox, then
   obtain bounded read-only live preflight evidence.
5. Resolve drift or validation failure. A stale model, plan, snapshot, or target
   cannot proceed.
6. As a deployer, type the exact target name and separately acknowledge
   destructive work.
7. Queue one durable apply using an idempotency key; closing the UI does not
   cancel accepted work.
8. Observe recovery and verification states until a persisted post-apply
   snapshot proves exact convergence or reports a truthful non-success state.

## Functional requirements

| ID | Requirement | Current status | Release evidence |
|---|---|---|---|
| FE-PRD-001 | Persist a project-scoped desired model as immutable numbered revisions; reject stale saves. | **Implemented** in backend | API concurrency and authorization tests |
| FE-PRD-002 | Compile one exact revision against one exact connection and succeeded snapshot; the browser supplies intent, not executable SQL. | **Implemented** for a narrow PostgreSQL subset | Model/plan API and compiler tests |
| FE-PRD-003 | Every admitted target difference becomes an operation or blocker; a blocked plan contains no executable statements while retaining independent supported deltas as review-only proposals. | **Implemented** for the current canonical subset | Per-field mutation tests and realistic snapshot fixtures |
| FE-PRD-004 | Show immutable plan provenance, executable or review-only proposed SQL, risk, preconditions, blockers, digest, and expiry. | **Partially implemented**; API and standalone read-only review panel exist, while workflow orchestration and browser E2E are absent | Typed API contract and UI tests |
| FE-PRD-005 | Dry run executes exact stored-plan DDL only in an isolated compatible sandbox; production receives bounded reads only. | **Partially implemented:** execution core, provider-neutral durable handler with bounded sandbox/preflight stage deadlines, dedicated ephemeral PostgreSQL 14–18 database round trip, and a test-owned composition over separate sandbox and read-only target connections exist; an expired-attempt takeover resumes preflight after committed sandbox convergence without replay. Deployed provisioning, credential resolution, isolation/lifecycle, startup, process restart, and worker operation remain Planned | Network/egress-isolation, cleanup, deployment identity, and live no-DDL evidence |
| FE-PRD-006 | Detect base drift before dry run and again under apply-time locks before DDL. | **Partially implemented:** the isolated dry-run core validates the materialized base digest before DDL; apply-time locked revalidation remains **Planned** | Injected-drift and concurrency tests |
| FE-PRD-007 | Require deployer authority, exact current model revision, plan/dry-run digests, typed target confirmation, and destructive acknowledgement. | **Partially implemented**; the non-dispatched apply-intent route locks the model row, rejects `stale_revision`, and persists those exact bindings, while apply-time target revalidation/execution remain Planned | Role/tamper/race tests |
| FE-PRD-008 | Persist idempotent dry-run/apply resources and append-only evidence; never auto-replay an ambiguous apply. | **Partially implemented**; dry-run and non-dispatched apply intents/resources/evidence, a PostgreSQL 14–18 same-key apply-intent race, DB-durable hashed attempt CAS, exact consumer-to-attempt binding, terminal cancellation acknowledgement, terminal redelivery settlement without sandbox/preflight replay, and pre-live-read attempt-expiry takeover without sandbox replay exist; application startup wiring, process/container recovery, commit-uncertainty reconciliation, and apply execution remain absent | Live-executor crash/no-replay, state-machine, and exact-owner lease tests |
| FE-PRD-009 | Re-introspect after known commit and compare a persisted verification snapshot to the desired digest. | **Planned** | End-to-end empty-residual-diff assertion |
| FE-PRD-010 | Provide a keyboard-operable five-stage review/dry-run/apply/verification journey without reusing the export modal. | **Planned** | Accessibility, component, and browser E2E tests |

## Non-functional requirements

| ID | Requirement | Gate |
|---|---|---|
| FE-NFR-001 Safety | No arbitrary browser SQL on the graphical model-to-apply path; unsupported semantics fail closed. | Mandatory |
| FE-NFR-002 Integrity | Revision, plan, approval, dry run, run, and verification evidence bind exact digests and immutable IDs. | Mandatory |
| FE-NFR-003 Tenancy | Cross-project and unauthorized resource identities are uniformly masked; roles are enforced server-side. | Mandatory |
| FE-NFR-004 Operability | Timeouts, cancellation boundaries, recovery, `outcome_unknown`, cleanup, and kill-switch procedures are documented and tested. | Mandatory |
| FE-NFR-005 Privacy | DSNs, credentials, row values, complete desired JSON, and raw SQL batches do not enter logs, events, queue payloads, or metrics. | Mandatory |
| FE-NFR-006 Accessibility | The workflow meets WCAG 2.2 AA interaction/status/error expectations and completes by keyboard. | Mandatory |
| FE-NFR-007 Compatibility | PostgreSQL 14–18 capability is explicit; unknown contract versions and operation kinds are rejected. | Mandatory |
| FE-NFR-008 Verification | Exact release-head backend/frontend tests, typing, build, security checks, PostgreSQL integration, and browser E2E pass. | Mandatory |

## Success measures and release gates

The following are binary release gates, not aspirational dashboards:

- zero paths from graphical intent to execution that accept browser SQL;
- zero admitted canonical changes without an operation or blocker;
- zero live DDL during dry run;
- zero DDL after detected stale revision, expired plan, failed dry run, or drift;
- one effective run for concurrent identical idempotency submissions;
- zero automatic replay after execution reaches an ambiguous commit boundary;
- empty semantic residual diff for every supported successful round trip;
- all documented exact-head quality and accessibility checks pass.

Production baselines for plan volume, stage duration, timeout rate, drift rate,
and failure classes do not yet exist. Operators must establish them during a
non-production pilot; this document does not invent numeric SLOs before runtime
evidence exists.

## UX acceptance

- The UI labels current support as partial and never calls legacy rollback
  validation an isolated dry run.
- Plan SQL is read-only. A user changes intent by editing and saving a successor
  model, not by editing SQL text.
- Blockers name the unsupported object and prevent dry run/apply actions.
- Risk is conveyed by text and structure, not color alone.
- Progress and all terminal states use accessible names/live regions; closing a
  modal never misrepresents or silently cancels durable work.
- `outcome_unknown`, `verification_failed`, `failed_rolled_back`, and
  `applied_with_drift` remain visually and semantically distinct.

## Non-goals for the first production slice

- arbitrary SQL editing or execution;
- heuristic rename inference;
- DML or automated backfills;
- scheduled or automatic production apply;
- automatic rollback generation;
- Snowflake or MySQL live apply;
- non-transactional/online operations such as `CREATE INDEX CONCURRENTLY`;
- claims of compliance certification based only on repository controls.

## Delivery phases

| Phase | Scope | Status |
|---|---|---|
| 1. Plan authority | Model revisions, canonical digest, snapshot adapter, structured plan persistence, deployer role | **Partially implemented in this branch** |
| 2. Validation | Plan retrieval, isolated sandbox, live read-only preflight, drift evidence | **Partial:** plan retrieval, signed-plan sandbox execution core, strict convergence, bounded live-read primitive, and durable attempt ownership exist. Consumer-to-attempt binding is **Implemented**; sandbox lifecycle, application startup wiring, credential binding, and worker execution remain **Planned**. |
| 3. Apply/recovery | Durable runs/events, approval, locks/timeouts, idempotency, reconciliation | **Partial foundation:** run/event/outbox identity, cancellation intent and terminal acknowledgement, exact-owner attempt leases, terminal dry-run redelivery settlement, and an exact non-dispatched apply intent exist; live dispatch/execution/recovery remain Planned |
| 4. Convergence UI | Post-apply snapshot/diff plus accessible frontend workflow | **Partially implemented:** review, dry-run intent, non-dispatched apply intent, run status/audit, polling, and cancellation surfaces exist; apply execution/recovery/convergence and composed E2E remain Planned |

No phase may describe the end-to-end feature as production-ready before every
release gate for phases 1–4 is satisfied.
