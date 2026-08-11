# Forward Engineering Documentation Audit

- **Audit status:** Reconciled with the 2026-08-11 working tree
- **Baseline:** `bcce75a64b9b658e14fe046ba4149aa8f53e94e2`
- **Runtime conclusion:** Phase 1 control plane is Partially implemented and not production-ready
- **Documentation conclusion:** Adequate to continue bounded implementation; insufficient to authorize production apply

## Executive assessment

Before this update, the repository did **not** contain a sufficient canonical
documentation set for the conversation's end-to-end forward-engineering goal.
It had a detailed approved-scope design at
`docs/superpowers/specs/2026-08-09-forward-engineering-design.md`, but no root
architecture, canonical PRD/TRD, ADR index, normative contract, current/planned
UML and ERD, feature threat model, test strategy, standards baseline, or
operational recovery runbook. The baseline README also described forward
engineering primarily as snapshot DDL export/diff and left safe workflow work
as a roadmap item.

After this update, the repository has a coherent source-controlled set that:

- distinguishes **Implemented**, **Partially implemented**, **Planned**, and
  **Rejected** behavior;
- describes the current model/revision/plan vertical slice without claiming
  sandbox, durable apply, convergence, or frontend support;
- records the key architecture decisions and rejected unsafe alternatives;
- separates implemented model/plan/run/event persistence from planned worker,
  sandbox, preflight, apply, and convergence entities;
- traces normative invariants to current code, tests, and documents; and
- makes production blockers, security residuals, verification evidence, and
  no-replay recovery explicit.

That is sufficient documentation for Phase 1 review and sequenced
implementation. It is deliberately not sufficient production evidence. The
largest remaining gaps are runtime code, real PostgreSQL/fault-injection/E2E
tests, operations, accessibility, and legacy live-route containment—not missing
prose.

## Audit method

Artifacts were evaluated against five questions:

1. **Discoverability:** Is there one indexed canonical location, and can a new
   contributor find it from the README?
2. **Truthfulness:** Does it match current routes, models, migrations, tests,
   support boundaries, and absence of runtime components?
3. **Decision completeness:** Are safety-critical choices, alternatives,
   consequences, and implementation status recorded?
4. **Traceability:** Can each normative requirement be followed to code, test,
   and operational or planned evidence?
5. **Release usefulness:** Does it define failure, drift, timeout, approval,
   recovery, accessibility, and verification gates strongly enough to prevent a
   premature “done” claim?

Adequacy labels in this audit mean:

- **Adequate:** Sufficient for its current design/implementation purpose and
  explicitly bounded.
- **Partial:** Useful but missing runtime evidence, cross-link, or settled
  contract detail.
- **Stale:** Contradicts or materially predates current implementation truth.
- **Missing:** No scoped repository artifact existed at the audit point.
- **N/A:** Not applicable to this product boundary.

## Before/after adequacy matrix

| Artifact | Baseline assessment | Repository artifact after update | After assessment | Remaining limitation |
|---|---|---|---|---|
| Product outcome and requirements | **Partial:** UI product spec covered the existing editor, not safe model-to-verification workflow. | [PRD](PRD.md) | **Adequate for target scope** | Forward UI and production metrics are Planned, so acceptance has no runtime evidence yet. |
| Technical requirements and support contract | **Missing** as a canonical current-vs-target TRD. | [TRD](TRD.md) and [v1 contract](contracts/forward-engineering-v1.md) | **Adequate for Phase 1** | Planned run schema/API/error envelope must be frozen with implementation. |
| Architecture | **Missing** at repository root; detailed design was not a current component index. | [Architecture](../ARCHITECTURE.md) | **Adequate** | Runtime sandbox/worker/network topology remains Planned and needs deployment evidence. |
| Architecture decisions | **Missing:** safety decisions existed inside one design narrative, without indexed ADR status. | [ADR index](adr/README.md) and ADR-0001–0005 | **Adequate** | Future non-transactional execution, secret-manager/key separation, and any exception need new ADRs. |
| UML/component/sequence/state views | **Missing** | [UML](UML.md) | **Adequate** | Durable-run persistence and authenticated polling are Implemented; planned executor state machines have no worker implementation yet. Repository Mermaid is authoritative; FigJam is companion only. |
| Metadata ERD | **Missing** | [Data model](DATA_MODEL.md) | **Adequate for current physical schema** | Planned execution bindings, indexes, and retention need migration review. |
| API and invariant contract | **Partial:** design route names and desired shapes were not separated from current routes. | [v1 contract](contracts/forward-engineering-v1.md) | **Adequate for current truth** | Public route spelling, RFC 9457 problem details, and planned run routes remain unresolved. |
| Security/threat model | **Partial:** general API checklist and vulnerability reporting existed, not a DDL-specific trust/abuse model. | [Forward threat model](security/forward-engineering-threat-model.md) | **Adequate for design review** | Several high-risk controls are Planned; no production risk acceptance is granted. |
| Operational/runbook | **Missing** | [Forward runbook](runbooks/forward-engineering.md) | **Partial by design** | Run states, alerts, kill switch, timeouts, sandbox, and evidence bundle are not implemented or drilled. |
| Test strategy and release evidence | **Missing** as a scoped strategy; scattered tests existed. | [Test strategy](TEST_STRATEGY.md) | **Adequate as strategy; evidence incomplete** | Real PostgreSQL 14–18, fault injection, composed E2E, accessibility, and forward coverage enforcement remain blockers. |
| Standards and research baseline | **Partial:** sources were scattered and version/status distinctions were absent. | [Standards](STANDARDS.md) | **Adequate** | This is a baseline, not compliance certification; scoped ASVS evidence must be produced per release. |
| Frontend functional/accessibility specification | **Stale for forward engineering:** existing UI spec does not include the five-stage safe workflow. | PRD, design spec, UML and test strategy define target behavior. | **Partial** | No component-level forward UI spec, implementation, screenshots, Figma component design, or E2E evidence exists. |
| Discoverability/indexing | **Partial:** no canonical forward document index. | README “정본 설계 문서”, architecture references, ADR index | **Adequate** | Required-document and core-link presence now has a contract test; full Markdown/Mermaid parsing remains a gate. |
| Code-to-doc traceability | **Missing** | This audit, TRD traceability tables, and `test_documentation_contract.py` | **Adequate for current slice** | Exact release-result links and broader semantic drift enforcement remain Planned. |

## Implementation inventory used by this audit

### Implemented in the current working tree

- `schema_model`, `schema_model_revision`, and `migration_plan` ORM/Alembic
  resources with project, actor, revision, snapshot, connection, digest, and
  expiry provenance.
- Canonical PostgreSQL 14–18 model validation/digest and exact identifier
  preservation for the admitted subset. Safe aliases are normalized to
  PostgreSQL catalog spelling; non-convergent serial pseudo-types are rejected.
- Snapshot adapter handling for real introspection keys used by defaults and
  primary-key deferrability, acceptance of represented primary-key backing
  indexes, current capability-version enforcement, repeatable-read capture,
  and rejection of dropped slots or unsupported constraints/catalog features.
- Deterministic structured plan compilation for the admitted create/drop/add,
  type, and nullability subset, including explicit risk, privilege,
  preconditions, and blockers.
- Explicit blockers—rather than silent omission—for schema removal, table and
  column comments, existing-column reordering, non-appended new columns, and
  existing primary-key changes. Any blocker makes executable `statements`
  empty, while independently supported deltas remain review-only
  `proposed_statements`; the risk summary includes those proposals.
- Every admitted `ALTER COLUMN ... TYPE` is conservatively classified
  destructive with possible rewrite, scan, and data-loss risk.
- Current schema-model create/get/revise routes and plan-create route with role,
  tenancy, snapshot/connection, size, and strong revision-UUID ETag
  optimistic-concurrency checks.
- Immutable plan retrieval with persisted-plan digest verification, plus durable
  `migration_run`/`migration_run_event` persistence, internal idempotent dry-run
  creation, optimistic state/cancellation writers, tamper-evident event chains,
  and authenticated integrity-checked run polling.
- `deployer` between editor and owner, plus deployer gating of persistent legacy
  `apply-sql` using a primary-session authorization read.
- Existing general controls for CSRF, credentialed CORS (allowing `If-Match`
  and exposing `ETag`),
  rate limiting, encrypted DSNs, DSN redaction, target allowlisting, restricted
  address rejection, DNS resolution/IP pinning, and optional verified-hostname
  TLS.

### Implemented and planned execution boundaries

- **Implemented — scheduled relay lifecycle and UUID-only publication:** the
  opt-in application task publishes only `migration_run_uuid` from one fresh
  caller-owned metadata transaction per bounded attempt. Public dry-run
  creation, atomic identifier-only outbox, lock-scoped claim/publish-state CAS,
  and cancellation intent are also implemented.
- **Planned — queue consumer, worker execution, failover, and retention:** no
  signal consumer loads plans or credentials, accesses a target, or executes
  SQL. Sandbox/preflight/apply workers and public apply-run creation remain
  absent.
- Isolated version-compatible sandbox execution and live read-only preflight.
- Target fingerprint revalidation, advisory and object locking, apply-time data
  preconditions, stored-plan executor, and explicit transactional segment
  recovery.
- Crash/restart recovery and no-replay apply reconciliation. Atomic outbox
  persistence, lock-scoped claim/publish-state CAS, UUID-only publication,
  internal idempotency, compare-and-swap transitions, cancellation intent,
  and append-only event evidence are implemented.
- Verification snapshot, residual diff, convergence classification, alerts,
  kill switch, retention, and tested incident procedure.
- Forward browser/API client, modal workflow, polling, accessibility, and every
  honest terminal-state presentation.

## Requirement → code → test → document traceability

The invariant IDs come from the
[forward-engineering v1 contract](contracts/forward-engineering-v1.md). A dash
means the runtime artifact does not yet exist; a design document is not counted
as code or test evidence.

| Invariant | Current code | Current tests | Authoritative documents | Status / unresolved proof |
|---|---|---|---|---|
| FE-INV-001: browser intent; server SQL authority | `backend/app/forward/schema_model.py`; `backend/app/forward/migration_plan.py`; schema-model/plan APIs | `test_forward_schema_model.py`; `test_forward_migration_plan.py`; forward API tests | [ADR-0001](adr/ADR-0001-server-authoritative-planning.md), [TRD](TRD.md) | **Partially implemented:** plan path is server-owned; executor/UI absent and legacy browser SQL endpoint remains transitional. |
| FE-INV-002: canonical append-only revision | `models.py`; migration `0008`; `api/schema_models.py` | `test_forward_schema_model.py`; `test_api_schema_models.py` | [Contract §3–5](contracts/forward-engineering-v1.md), [Data model](DATA_MODEL.md) | **Implemented through API;** database update-prevention trigger absent. |
| FE-INV-003: exact plan provenance | `models.py`; migration `0009`; `api/migration_plans.py` | `test_api_migration_plans.py` | [TRD](TRD.md), [Data model](DATA_MODEL.md) | **Implemented control plane;** execution-time expiry/digest enforcement is Planned. |
| FE-INV-004: every difference is operation or blocker | `forward/migration_plan.py`; `forward/snapshot_adapter.py` | compiler comment/order/schema-removal/PK blocker and review-only proposal tests; snapshot default/constraint/index/partition tests | [Contract §6–7](contracts/forward-engineering-v1.md), [ADR-0001](adr/ADR-0001-server-authoritative-planning.md) | **Implemented for current canonical subset:** blocked plans have no executable statements but retain supported deltas as non-executable proposals with risk; exhaustive real-catalog dependency proof is missing, so the release invariant remains Partial. |
| FE-INV-005: isolated DDL and live read-only preflight | — | — | [ADR-0002](adr/ADR-0002-isolated-dry-run-and-preflight.md), [UML](UML.md), [Threat model](security/forward-engineering-threat-model.md) | **Planned release blocker.** Legacy rollback-on-live is explicitly not evidence. |
| FE-INV-006: fingerprint revalidation for dry run/apply | Plan stores base digest only | — | [TRD](TRD.md), [Runbook](runbooks/forward-engineering.md) | **Planned release blocker.** |
| FE-INV-007: in-lock data preconditions | Compiler emits precondition metadata | Compiler asserts metadata kinds/risk | [ADR-0003](adr/ADR-0003-plan-execution-segmentation.md), [Runbook](runbooks/forward-engineering.md) | **Planned runtime enforcement;** concurrency proof absent. |
| FE-INV-008: one transactional segment | Current compiler marks admitted statements transactional | Compiler structured-plan tests | [ADR-0003](adr/ADR-0003-plan-execution-segmentation.md), [TRD](TRD.md) | **Planned executor/rollback proof.** Segment metadata/postconditions are not yet persisted. |
| FE-INV-009: durable idempotent run, no apply replay | `models.py`; migration `0010`; `forward/migration_run.py`; `jobs/migration_dispatch_relay.py`; `api/migration_runs.py` | `test_forward_migration_run.py`; `test_migration_dispatch_relay.py`; `test_migration_dispatch_lifecycle.py`; `test_api_migration_runs.py` | [ADR-0004](adr/ADR-0004-durable-runs-and-recovery.md), [Data model](DATA_MODEL.md), [Runbook](runbooks/forward-engineering.md) | **Partially implemented:** durable identity, atomic identifier-only dispatch outbox, dry-run creation, opt-in scheduled UUID-only publication, CAS/cancellation writers, event chain, and polling exist; queue consumption, deployment failover, execution, and apply no-replay recovery remain blockers. |
| FE-INV-010: deployer and evidence-bound approval | `permissions.py`; persistent legacy apply requires deployer | `test_permissions.py`; `test_api_apply_sql.py` | [ADR-0005](adr/ADR-0005-authority-approvals-and-convergence.md), [PRD](PRD.md) | **Partially implemented:** role boundary exists; exact dry-run/typed/destructive approval binding is Planned. |
| FE-INV-011: no DSN/secret/raw SQL in queue/events/browser | Encrypted connection/redaction boundaries; `migration_run_dispatch` identifier-only schema; `forward/migration_run.py`; `jobs/migration_dispatch_relay.py`; sanitized worker failure codes | run/outbox schema, UUID-only publication against digest-pinned real Valkey, evidence, and worker dispatch leakage regressions; DSN guard/redaction and snapshot error tests | [Threat model](security/forward-engineering-threat-model.md), [Data model](DATA_MODEL.md) | **Partially implemented:** dispatch storage and the real Valkey signal contain no execution material, while durable evidence and generic worker failures reject secret-bearing content; future consumer, sandbox/apply payloads, and browser surfaces remain unproved. |
| FE-INV-012: only matching verification snapshot is verified | — | — | [ADR-0005](adr/ADR-0005-authority-approvals-and-convergence.md), [UML](UML.md), [Runbook](runbooks/forward-engineering.md) | **Planned release blocker.** |
| FE-INV-013: uniform cross-project masking | Current model/plan/connection routes | focused model/plan/apply tests | [Contract §9](contracts/forward-engineering-v1.md), [Threat model](security/forward-engineering-threat-model.md) | **Partially implemented:** full HTTP role/IDOR matrix and future resources absent. |
| FE-INV-014: unknown fields/kinds/versions fail closed | Canonicalizer, snapshot/compiler boundary, and exact run/event state contracts | unknown-field/unsupported-feature/version and invalid run/event tests | [Contract §2, §4, §7](contracts/forward-engineering-v1.md), [Test strategy](TEST_STRATEGY.md) | **Partially implemented:** current model/plan/run boundaries fail closed; sandbox/apply executor dispatch remains absent. |

## Unresolved gaps and priority

### P0 — production release blockers

| Gap | Why documentation cannot close it | Required evidence |
|---|---|---|
| Queue consumption/worker execution and apply-run API | Atomic identifier-only outbox persistence, authorized dry-run creation/cancellation, scheduled bounded UUID-only queue publication, CAS writers, and integrity-checked polling exist, but consumer/worker execution and public apply creation are unavailable. | Deployment relay failover, consumer restart/cancellation integration tests, approval-bound apply creation |
| Isolated sandbox and read-only preflight | A rollback on production still creates lock/scan/rewrite risk. | Network/credential isolation proof, real PostgreSQL sandbox convergence and live no-DDL audit |
| Drift-safe executor | Stored plan metadata alone does not acquire locks, enforce preconditions, bound time, or roll back. | Versioned stored-plan dispatch, lock/timeout/concurrency/rollback integration tests |
| Idempotency and uncertain-commit recovery | A lease retry can duplicate destructive DDL unless apply is never replayed after the boundary. | Crash/fault injection and reconciliation to `verified`, `not_applied`, or `outcome_unknown` |
| Post-apply convergence | Commit acknowledgement is not desired-state proof. | Dedicated verification snapshot and exact/third-digest E2E assertions |
| Product UI and accessibility | Users cannot safely review, authorize, observe, or recover through the current frontend. | Typed API client, forward modal, state polling, WCAG 2.2-oriented automation and manual evidence |
| Real PostgreSQL/version evidence | In-memory fixtures cannot prove real `pg_catalog`, SQL, lock, privilege, or transaction behavior. | PostgreSQL 14–18 matrix, adversarial catalogs, external writers, representative sizes |
| Kill switch, alerts, recovery drill | Operators cannot contain or classify a live incident using design prose. | Implemented gate, metrics/alerts, backup/restore posture, non-production game day |
| Legacy live-route retirement/containment | The transitional path bypasses immutable plan, dry-run, evidence, and convergence authority. | Disable/retire decision, ingress/app gate, regression tests and operator procedure |

### P1 — contract and maintainability gaps

- Decide whether `POST /api/schema-models/by-project/{project_space_uuid}` is
  the public v1 route or whether the project-nested design alias will be added.
- Standardize forward errors using the selected RFC 9457-compatible contract;
  current routes commonly return string `detail` values.
- Add database-enforced immutability or equivalent privileged write controls
  for model revisions, plans, and future events.
- Add forward modules/APIs to explicit statement and branch coverage scope and
  enforce the 100% owned-code policy in CI.
- Extend the implemented required-document/core-link/route contract test to
  validate every internal link, status label, Mermaid parse/render, ADR index
  consistency, and stale implementation claims.
- Create a frontend component/accessibility specification when implementation
  starts; the existing `docs/ui-ux/product-spec.md` remains useful for the
  current ERD editor but does not describe forward engineering.
- Define outbox semantics, same-tenant enforcement, retention, deletion policy,
  and an independently anchored audit sink before enabling workers. Run/event
  columns, idempotency, sequencing, indexes, and the in-database digest chain
  are implemented in ORM/Alembic and remain subject to reviewed migrations.
- Produce a release-scoped ASVS 5.0.0 applicability/evidence matrix; the
  standards document intentionally makes no certification claim.

## Documentation ownership and drift rules

| Change | Documents that must change in the same PR |
|---|---|
| User outcome, role, or release scope | PRD, contract, traceability audit; ADR if authority changes |
| API route, request/response, error, state, or status meaning | TRD, contract, UML sequence/state, tests |
| ORM/Alembic entity, FK, uniqueness, retention, or delete behavior | Data model/ERD, TRD, runbook, migration tests |
| Compiler grammar, operation kind, risk, blocker, or PostgreSQL version | Contract support matrix, TRD, ADR if recovery changes, test matrix |
| Sandbox/network/credential topology | Architecture, UML, threat model, runbook, deployment tests |
| Executor transaction, lock, timeout, retry, cancellation, or recovery | ADR, contract, UML states, threat model, runbook, fault tests |
| Frontend review/approval/recovery flow | PRD, UML, UI spec, test strategy and accessibility evidence |
| Standards version or compliance statement | Standards, threat model, test/release evidence; never update by unsupported claim |

Implementation status must change only with a code/test evidence link. An
accepted ADR means the direction is approved; it never means the runtime is
complete. Figma/FigJam may aid review, but repository Mermaid, code,
migrations, tests, and versioned documents remain authoritative.

## Final sufficiency decision

| Question | Decision |
|---|---|
| Are ADR, PRD, TRD, Architecture, UML, and ERD now present and internally coherent for Phase 1? | **Yes — Adequate**, subject to normal PR review and link/diagram validation. |
| Do they distinguish current implementation from the accepted target? | **Yes.** Model/revision/plan are current; sandbox/run/apply/convergence/UI are Planned; browser arbitrary SQL and production rollback-as-dry-run are Rejected target behavior. |
| Is code/test/document traceability sufficient to select the next implementation slice? | **Yes.** P0 work and invariant gaps are explicitly mapped. |
| Is the feature production-ready or safe to enable because the documentation is now extensive? | **No.** Runtime, PostgreSQL, fault, security, accessibility, and operational gates remain open. |
| Can a future “done” claim rely on these documents alone? | **No.** Exact-head machine and operational evidence is mandatory. |

The correct next exit is not more unbounded documentation. It is to implement
the highest-risk P0 vertical slice under these contracts, update status and
traceability with real evidence, and repeat the audit before production
enablement.

## Canonical document index

- [Architecture](../ARCHITECTURE.md)
- [PRD](PRD.md)
- [TRD](TRD.md)
- [ADR index](adr/README.md)
- [Forward-engineering v1 contract](contracts/forward-engineering-v1.md)
- [UML](UML.md)
- [Data model and ERD](DATA_MODEL.md)
- [Threat model](security/forward-engineering-threat-model.md)
- [Operational runbook](runbooks/forward-engineering.md)
- [Test strategy](TEST_STRATEGY.md)
- [Standards baseline](STANDARDS.md)
- [Detailed approved design](superpowers/specs/2026-08-09-forward-engineering-design.md)
