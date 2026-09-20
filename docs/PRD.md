# Product Requirements Document

Product: pg-erd-cloud
Status: living authority
Last evaluated: 2026-08-09

## Product outcome

pg-erd-cloud gives developers and data architects a governed visual workflow
for discovering, understanding, reviewing, sharing, and ultimately changing
database schemas. It must work as a standalone product and as a versioned
module in the ContextualWisdomLab ecosystem.

The commercial outcome is not "generate some SQL." It is to turn an editable
schema intent into explainable, reviewable, recoverable database change with
evidence that the target converged to the approved model.

## Users and jobs

| Persona | Primary job | Failure they must avoid |
| --- | --- | --- |
| Data architect | Model entities, relationships, constraints and naming | Losing semantic detail or mistaking a visual draft for deployable DDL |
| Application engineer | Compare current and desired schemas and export artifacts | Applying stale, incorrectly ordered or unsupported SQL |
| DBA/platform engineer | Understand lock, rewrite, privilege and recovery impact | Production blocking, partial apply, drift race or unverifiable recovery |
| Reviewer/auditor | Inspect immutable intent, approvals, execution and result | Approval that is not bound to the exact plan and target |
| Collaborator | Review a read-only ERD without project membership | Accidental disclosure, editing, paid LLM invocation or diagnostic leakage |

## Product boundaries

### In scope

- Project-scoped target connections, snapshots, ERD views and annotations.
- PostgreSQL-first catalog introspection and semantic schema models.
- Deterministic exports and schema-diff evidence.
- Accessible visual editing and read-only bearer sharing.
- Governed Forward Engineering for supported PostgreSQL constructs.
- Versioned integration contracts for CI and other CWL services.

### Explicitly outside the authority boundary

- `downstream`: identity lifecycle owned by an external OIDC provider.
- `downstream`: centralized model routing owned by contextual-orchestrator.
- `downstream`: enterprise WAF/IDS and external secret manager operation.
- `out_of_scope`: arbitrary SQL console or general database administration.
- `out_of_scope`: silent best-effort conversion of unsupported database
  constructs.
- `out_of_scope`: blanket PII masking that removes schema/business utility.

## Capability status

| Capability | Lifecycle | Product evidence |
| --- | --- | --- |
| Authentication, projects, membership and encrypted connections | Backend/API `implemented_on_main`; browser login `planned` | FastAPI APIs, ORM models and tests; SPA has no non-demo token flow |
| Asynchronous reverse-engineering snapshots | `implemented_on_main` with recovery gap | PostgreSQL queued state and connector tests; claimed jobs have no lease/reclaim |
| ERD canvas and local table/relationship/group editing | Local editing `implemented_on_main`; live-Figma UI alignment `active_pr`; durable edited-model persistence `planned` | React Flow application, PR #824 and missing model revision boundary |
| Live-Figma-aligned shell, inspector, dialogs and responsive behavior | `active_pr` | PR #824 at its exact current head |
| Hardened public read-only share viewer | `active_pr` | PR #824 at its exact current head |
| Snapshot diff, migration SQL and coarse risk report | `implemented_on_main` | `/diff`, `/migration.sql`, `/migration-safety` |
| Client-authored allow-listed synchronous apply | `deprecated` | `/api/connections/{id}/apply-sql`; not production Forward Engineering |
| MySQL/MariaDB introspection | `research_only` backend adapter | Adapter/tests exist, but driver packaging, API schema, frontend and dialect contracts are incomplete |
| Versioned editable server-side schema model | `planned` | FE-100 |
| Immutable structured plan and isolated dry-run | `planned` | FE-110 through FE-130 |
| Authorized durable apply and convergence proof | `planned` | FE-140 through FE-180 |

## Functional requirements

### Discovery, modeling and collaboration

| ID | Requirement | Acceptance | Lifecycle |
| --- | --- | --- | --- |
| DISC-010 | An editor can register a project-scoped target connection without exposing its DSN after creation. | Ciphertext/nonce at rest; IDOR-safe APIs; secrets absent from logs and responses. | `implemented_on_main` |
| DISC-020 | An editor can request a non-blocking schema snapshot. | Queued state survives restart, workers claim exclusively, and successful catalog JSON is stored; in-flight crash recovery is REL-010. | `implemented_on_main` with known recovery gap |
| MODEL-010 | A modeler can inspect and edit tables, columns, relationships, groups and layouts. | Main provides transient local editing; PR #824 aligns interaction/UI; acceptance requires changes to survive the explicit durable model boundary. | Local editing `implemented_on_main`; alignment `active_pr`; persistence `planned` |
| SHARE-010 | An owner can create and revoke an expiring read-only bearer view. | Only successful allowlisted snapshots; configurable expiry, owner-only project-scoped API revocation, no edit control, private diagnostics or live LLM work. UI revocation remains a stated gap. | `active_pr` |
| EXPORT-010 | A user can produce deterministic supported artifacts. | Current code deterministically renders a stored snapshot at one code revision; compiler-version binding is required by FE-110. | Current exports `implemented_on_main`; version binding `planned` |

### Governed Forward Engineering

| ID | Requirement | Acceptance | Lifecycle |
| --- | --- | --- | --- |
| FE-100 | Persist every editable desired schema as an immutable revision. | Revision has project, parent revision, actor, timestamp, normalized model and digest. | `planned` |
| FE-110 | Compile a stored revision and observed target into one structured migration plan. | Browser cannot supply executable SQL authority; every statement has dependencies, risk and support status. | `planned` |
| FE-120 | Explain semantic diff and operational impact. | Data-loss, lock, rewrite, validation, privilege, version, extension and non-transactional risks are explicit and non-color-only. | `planned` |
| FE-130 | Prove syntax/executability in an isolated compatible PostgreSQL environment. | Destructive/locking DDL is never tested against production under the label "harmless dry-run." | `planned` |
| FE-140 | Bind approval to immutable intent and target. | Approval covers tenant, connection, model revision, target fingerprint, compiler/version matrix, ordered statement digest and expiry. | `planned` |
| FE-150 | Revalidate immediately before apply. | Drift, privileges, server capabilities and approval binding fail closed before the first write. | `planned` |
| FE-160 | Execute through a durable serialized job. | Idempotency, bounded lock/statement timeouts, cancellation, retry and transactional/non-transactional segmentation are tested. | `planned` |
| FE-170 | Provide recovery evidence for every partial boundary. | Failed or cancelled jobs expose completed statements, durable evidence and safe operator guidance without secrets. | `planned` |
| FE-180 | Prove convergence. | Re-introspection matches the approved semantic model or reports exact residual drift. | `planned` |
| FE-190 | Fail closed for unsupported constructs. | Views, triggers, functions, types, extensions, partitioning, RLS, ownership, grants and other constructs have versioned capability outcomes; nothing is silently dropped. | `planned` |

## Non-functional requirements

| ID | Requirement | Target evidence | Lifecycle |
| --- | --- | --- | --- |
| SEC-010 | Least privilege and tenant isolation | Role tests, IDOR tests, scoped execution identities and threat-model traceability | Partly `implemented_on_main`; FE identity `planned` |
| SEC-020 | Credential and metadata confidentiality without blanket masking | Encryption, purpose-bound access, selective public redaction, retention and audit controls | Encryption `implemented_on_main`; share `active_pr`; retention/audit `planned` |
| REL-010 | Durable/restart-safe long work | Real worker restart, duplicate delivery, idempotency and recovery tests | `planned` beyond queued-state persistence |
| DATA-010 | Exact identifier and semantic preservation | Quoted, mixed-case, Unicode and multi-schema round-trip tests | Current exports partial; governed round-trip `planned` |
| PERF-010 | Bounded production impact | Plan estimates plus explicit `lock_timeout` and `statement_timeout`; no latency-first compromise of correctness | `planned` for FE |
| A11Y-010 | WCAG 2.2 AA-oriented user flows | Keyboard, focus, accessible-name, contrast and responsive browser evidence | Unit contracts `active_pr`; browser evidence incomplete |
| OBS-010 | Correlatable, privacy-preserving evidence | Request/job/plan IDs, metrics and tamper-evident audit chain; no DSN or body logging | Runtime metrics partial; plan/audit evidence `planned` |
| GOV-010 | CSAP/SOC 2 readiness without certification claims | Control/evidence mapping, change approval, access review, retention and incident records | `planned` |
| QUAL-010 | 100% meaningful owned production coverage and public docstrings | CI reports with no meaningless exclusion or mocked-away critical path | `planned`; current CI has no threshold |
| MOD-010 | Standalone and modular MSA operation | Versioned APIs/artifacts; no cross-repository database coupling | Standalone `implemented_on_main`; versioned ecosystem contracts partial |
| NAME-010 | Descriptive database object names | New objects use two-or-more-word `snake_case`; legacy exceptions have a compatibility migration | New target model `planned`; legacy exceptions inventoried |

## Release acceptance

A release claiming production-ready Forward Engineering is permitted only from
an exact protected-main head that passes required CI/security/coverage,
supported PostgreSQL round-trip and migration tests, accessibility,
package/SBOM/provenance, upgrade/rollback/recovery, and independent review.
Forward Engineering cannot be marketed as production-ready until FE-100
through FE-190 are `implemented_on_main` with linked evidence.
