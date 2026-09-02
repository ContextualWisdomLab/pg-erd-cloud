# Documentation Sufficiency and Coverage

Evaluation date: 2026-08-09
Question: Are the conversation's repository-relevant product, architecture,
data, design, security, verification, delivery, and continuation decisions
sufficiently captured, with external runtime authority clearly bounded?

## Verdict

Before this documentation set: **not sufficient**. The repository had useful
README, security, observability, integration, Figma and QA notes, but no
canonical PRD/TRD/architecture, ADR graph, UML behavior set, logical ERD, threat
model, test strategy, or requirement traceability. Contradictory lifecycle
claims could not be resolved mechanically.

After this set: **structurally sufficient for review, not sufficient to claim
all described behavior is implemented or release-ready**. Current and planned
truth are separated, durable decisions are captured, diagrams cover structure
and behavior, data models include naming debt, and requirements point to code
and tests. Residual implementation, live-browser, production-recovery, and
exact-head review evidence stays visibly incomplete.

The repository does not contain secrets or the executable ChatGPT automation
state. It now records the non-secret schedule/prompt behavior and evidence
contract in `docs/automation-contract.md`; enabled state and actual execution
remain externally verifiable `downstream` facts.

## Before/after coverage

| Concern | Before 2026-08-09 | Authority after this set | Evaluation |
| --- | --- | --- | --- |
| Product outcome/personas/scope | Scattered README/Figma copy | `docs/PRD.md` | Covered |
| Current vs target technology | README and source inference | `docs/TRD.md` | Covered with explicit gaps |
| System/context/component/deployment | No canonical architecture | `ARCHITECTURE.md`, `docs/UML.md` | Covered |
| Durable decisions/alternatives | No ADR index | ADR-0001 through ADR-0006 | Covered for repository-relevant decisions surfaced in this conversation |
| Current relational model | ORM/migrations only | `docs/ERD.md` current model | Covered; physical drift recorded |
| Planned FE data model | Conversation only | `docs/ERD.md` planned model | Covered as `planned` |
| Component/class/sequence/state UML | Absent | `docs/UML.md` | Covered |
| Security/privacy/abuse | Checklists without unified model | `docs/threat-model.md` | Covered; residual risks explicit |
| Verification and release evidence | CI files and QA notes | `docs/test-strategy.md` | Covered; missing E2E/coverage/integration gates explicit |
| Requirement-to-evidence mapping | Absent | `docs/traceability-matrix.md` | Covered and lifecycle-bound |
| Figma live authority | Newly drafted PR note | `docs/ui-ux/figma-contract.md`, ADR-0001 | Covered; visual signoff incomplete |
| Standards/research | Partial paper index | `docs/references.md` | Covered for current decisions |
| Operations/runbooks/SLOs | Partial observability/drift notes | `operations-runbook.md`, observability and release plan | Covered for safe current procedures; SLO/roster deployment inputs missing |
| API schema and compatibility | OpenAPI/source only | `API.md` plus generated OpenAPI | Covered at family/compatibility level; versioned public/FE schemas still planned |
| Forward Engineering construct support | Scattered code/tests | `forward-engineering-support-matrix.md` | Covered; governed column remains planned |
| Data retention/deletion/residency | Not defined | Threat-model gap | Missing owner/schedule |
| Release/rollback/recovery runbooks | Not canonical | `release-plan.md`, `operations-runbook.md` | Covered with unimplemented drills clearly labelled |
| Hourly review-to-merge-to-next loop and no-empty-queue rule | Conversation/external prompt only | `automation-contract.md`, ADR-0006 | Repository mirror covered; enabled schedule and runs remain external evidence |

## Conversation decisions captured

| Decision or correction | Durable location |
| --- | --- |
| Live Figma file is not empty; concrete screen nodes outrank conflicting free variables | ADR-0001 and Figma contract |
| Historical/deleted share/export node is not authority | ADR-0001 and Figma contract |
| Accessibility defects in Figma are corrected with documented semantic overrides | ADR-0001, Figma contract, test strategy |
| Public sharing is a smaller successful-only allowlisted bearer boundary with expiry/API revocation and no paid live LLM | ADR-0002, threat model, traceability |
| Public share currently represents stored snapshots, not transient edited graph/layout/groups | ADR-0002, UML, ERD |
| PostgreSQL is queue truth; Valkey is only a wake signal; in-flight recovery is missing | ADR-0003, UML, test strategy |
| Current generated DDL and deprecated apply validator are incompatible authorities | ADR-0004, TRD, traceability |
| Production FE must be server-owned model → plan → dry-run/preflight → approval → durable apply → convergence | ADR-0004, PRD, TRD, UML, ERD |
| All new database objects use descriptive two-or-more-word snake_case; legacy exceptions migrate compatibly | ERD, PRD NAME-010 |
| Documentation-only work is not implementation or release evidence | ADR-0005, traceability, this matrix |
| Product remains standalone and integrates through versioned contracts, not shared private tables | PRD MOD-010, Architecture |
| Hourly review → fix → verify → push/review → guarded merge → next work continues; an empty immediate queue is not a stop condition | ADR-0006 and automation contract; executable schedule/prompt remain external authority |

## Residual blockers and owners

| Priority | Gap | Required next artifact/evidence | Lifecycle |
| --- | --- | --- | --- |
| P0 | Every pushed head requires fresh security evidence for the `nanoid@3.3.17` remediation; this static document cannot certify a later head | Require all security gates on the exact PR head and remediate any new finding | `active_pr` gate |
| P0 | No independent review; draft-skipped reviewers | Ready-for-review state and completed head-bound review | `active_pr` |
| P0 | Browser/Figma comparison incomplete | Runtime screenshots and keyboard/responsive evidence | `active_pr` |
| P1 | No persisted immutable editable schema model | FE-100 API/migration/contract PR | `planned` |
| P1 | No server-owned plan/approval/executor/convergence | FE-110 through FE-190 implementation program | `planned` |
| P1 | Worker can strand running jobs | Lease/reclaim/idempotency/recovery design and tests | `planned` |
| P1 | ORM/migration JSON/index drift | Forward-only reconciliation migration and schema comparison gate | `planned` |
| P1 | SPA authentication is unwired outside demo assumptions | Versioned OIDC login/token flow and browser E2E | `planned` |
| P1 | Protected main omits CORS parity for implemented PUT/DELETE methods | Explicit method constant and preflight regression test are in PR #824; merge is still required | `active_pr` fix |
| P2 | Retention/deletion/residency and audit ownership undefined | Data-governance policy and operational runbook | `planned` |
| P2 | Drift script used unsupported cookie auth and implied it created snapshots | Bearer/API-key fix is `active_pr`; snapshot orchestration remains pipeline-owned | Mixed |

## Machine-checkable minimum

`backend/tests/test_documentation_contract.py` fails when a canonical authority
is missing, internal Markdown links break, ADR index entries disagree with
files, lifecycle vocabulary disappears, Mermaid coverage falls below the
declared structure/behavior/data minimum, Figma authority changes without the
known file/node contract, or legacy naming exceptions are lost without an
explicit migration update.

This is a floor, not a substitute for domain review. A logically wrong diagram
can still parse, and a planned requirement can still lack code; the
traceability matrix and exact-head review remain mandatory.
