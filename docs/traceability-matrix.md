# Requirement Traceability Matrix

Status date: 2026-08-09
Authority: requirement IDs in [PRD](PRD.md)

`Evidence` names exact protected-main paths unless an `active_pr` is stated.
An empty implementation cell is a gap, not permission to infer delivery from a
diagram or accepted design.

## Discovery, modeling and sharing

| Requirement | Lifecycle | Architecture/decision | Implementation evidence | Test/release evidence | Residual gap |
| --- | --- | --- | --- | --- | --- |
| DISC-010 | `implemented_on_main` | Architecture reverse flow; TM-040/050 | `backend/app/api/connections.py`, `security.py`, `pg_introspect/dsn_guard.py` | connection, security and DSN-guard test suites | Runtime credential registry and rotation evidence are `planned`. |
| DISC-020 | `implemented_on_main` with gap | ADR-0003; reverse sequence | `api/snapshots.py`, `jobs/worker.py`, `jobs/snapshot_job.py` | snapshot, worker and job tests | Claimed-job lease/reclaim, real restart and retry evidence are missing. |
| MODEL-010 | Local editing `implemented_on_main`; alignment `active_pr`; persistence `planned` | Figma contract; current UML component view | `frontend/src/App.tsx`, `frontend/src/erd`, modal components; dormant `diagram_views`/`annotations` APIs | Main edit tests plus PR Vitest interaction/style contracts | Full edited graph/layout/group/annotation state is transient and public share ignores it. |
| SHARE-010 | `active_pr` #824 | ADR-0002; public-share sequence; TM-020/030 | `backend/app/api/share.py`, `frontend/src/components/SharedDiagramView.tsx` | backend share tests cover primary-consistent revocation/path-scoped DTOs; frontend viewer tests cover read-only rendering | Visual browser signoff, UI revocation, rotation, access audit and typed/version-negotiated DTO remain. |
| EXPORT-010 | Current path `implemented_on_main`; version binding `planned` | TRD current baseline; ADR-0004 | `backend/app/ddl`, `backend/app/spec`, frontend export modules | export/migration/diff/component tests | Different export/diff/apply capability sets; no compiler version or immutable model binding. |

## Governed Forward Engineering

| Requirement | Lifecycle | Accepted design | Implementation evidence | Required acceptance evidence |
| --- | --- | --- | --- | --- |
| FE-100 | `planned` | ADR-0004; ERD `schema_model_revision` | None | Migration, normalized-model API, immutable revision/digest and authorization tests |
| FE-110 | `planned` | TRD Plan Compiler; planned sequence | None | One typed AST/plan used by diff, render, validate, dry-run, apply and audit |
| FE-120 | `planned` | PRD, TRD risk policy | Current `migration_safety.py` is only partial precursor | Versioned lock/rewrite/data/privilege/extension/nontransactional matrix |
| FE-130 | `planned` | ADR-0004 isolated dry-run | Deprecated transaction rollback is explicitly not evidence | Real disposable supported PostgreSQL versions and data-shape fixtures |
| FE-140 | `planned` | ERD `migration_approval` | None | Digest/target/revision/actor/policy/expiry binding and replay tests |
| FE-150 | `planned` | Planned sequence; TM-070 | None | Immediate target fingerprint, capability and privilege revalidation tests |
| FE-160 | `planned` | ERD `migration_execution_job`; job state | Current snapshot queue is not sufficient | Idempotency, per-target serialization, leases, timeouts, cancellation and segment tests |
| FE-170 | `planned` | `Recoverable` state; audit entity | None | Crash-at-every-boundary and operator recovery/rollback-truthfulness drills |
| FE-180 | `planned` | Planned sequence; TRD verify operation | None | Re-introspection and normalized semantic residual-diff proof |
| FE-190 | `planned` | Capability Policy | None | Fail-closed PostgreSQL-version construct matrix with no silent loss |

Current `schema_diff.py` compares a narrow table/column/type/nullability/PK/FK
and table-comment subset. `migration.py` has a different subset, full snapshot
export another, and the deprecated validator rejects much of their quoted,
commented, FK, and concurrent-index output. Those are precursors, not FE-100 to
FE-190 evidence.

## Non-functional requirements

| Requirement | Lifecycle/evidence | Main controls/tests | Gap that blocks full acceptance |
| --- | --- | --- | --- |
| SEC-010 | Partial `implemented_on_main` | OIDC/API keys, membership helpers, CSRF, role/IDOR suites, threat model | Primary-consistent auth for sensitive target actions and least-privilege FE identity |
| SEC-020 | Main encryption + share `active_pr` | DSN AES-GCM, redacted errors, fail-closed public-v1 key projection and unknown-field tests | Credential registry, retention/deletion, typed/version-negotiated public contracts and LLM governance |
| REL-010 | `planned` beyond queued persistence | PostgreSQL queue and exclusive claim tests | Real worker restart, reclaim, duplicate delivery, idempotency and recovery |
| DATA-010 | Partial precursors | Export/diff tests and quoted identifier rendering | Real PostgreSQL round-trip for exact Unicode/case/multi-schema semantics |
| PERF-010 | `planned` for write path | Request bounds and coarse migration safety | Estimates, lock/statement timeouts, large-table and contention evidence |
| A11Y-010 | Unit contracts `active_pr` | Dialog, focus, keyboard, semantic-token/style tests; Figma defect overrides | Real browser/assistive-tech and visual evidence at all required states |
| OBS-010 | Partial `implemented_on_main` | Structured logging, metrics, request/job identifiers | `/metrics` production routing, stuck-job alerting, plan events and integrity chain |
| GOV-010 | `planned` | ADR/change history and security gates are precursors | Control owner/evidence map, access review, retention and incident records |
| QUAL-010 | `planned` | Current pytest/Vitest/type/build CI | No CI coverage threshold; selected backend include list; no mutation or E2E gate |
| MOD-010 | Standalone `implemented_on_main`; ecosystem partial | Independent Compose/API and no cross-repo table coupling | Versioned artifact/API compatibility and supported submodule contract evidence |
| NAME-010 | Target policy `planned` | ERD inventory and documentation test | Four single-token columns, ambiguous creator fields, double-underscore objects, no migration |

## PR #824 exact-head release evidence

| Evidence | Evaluation of audited head `385af924` at 2026-08-09 11:33 UTC |
| --- | --- |
| Frontend/backend CI, Semgrep, CodeQL, central security jobs | Successful |
| Required Strix workflow | GitHub run `31306453112`, job `93227506608`, completed `failure`: the primary provider returned HTTP 429; fallback found vulnerable `nanoid@3.3.16`, could not map a structured artifact to changed files, and failed closed |
| Required OpenCode review | No completed formal GitHub review or review thread was present at the timestamp above |
| Independent review | None; CodeRabbit and Noema skipped because PR is draft |
| Figma/runtime visual signoff | Incomplete: live-node/code inspection exists, but the same-viewport runtime browser comparison remains blocked as recorded in `design-qa.md` |
| Documentation authorities | Absent from the audited head; at audit time they were uncommitted candidate work, not `active_pr` evidence. They become exact-head evidence only after push and re-audit |

The table is intentionally commit-bound. It must be refreshed after every push;
success on `385af924` cannot authorize a later documentation or dependency
commit. The current working tree resolves `nanoid` to patched `3.3.17` and has a
clean local npm audit, but that remediation is not promoted into this historical
head-bound table until it is committed, pushed, and rerun by the required gates.
