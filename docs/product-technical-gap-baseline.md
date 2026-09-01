# Product & technical gap baseline

**Last consolidated:** 2026-09-01 UTC (autonomous review/merge loop, iter22).

This document is the single tracker for the distance between what
pg-erd-cloud does today and a defensible first commercial release. It is
derived from the open `[Product Gap]` / `[Enterprise Gap]` / `[Performance
Gap]` / `[Security Gap]` / `[Epic]` issues (#946–#953), the code on
`main@8dc74692`, and the in-flight PRs that close pieces of each gap.

It supersedes the draft in PR #942 (which first introduces this file and is
currently blocked — see the commercial-readiness blocker below); the two
should be reconciled when either merges.

## What pg-erd-cloud is

A PostgreSQL-focused cloud ERD collaboration service. It reverse-engineers a
target database into immutable JSON schema snapshots, renders them as an
interactive ERD (React Flow), and forward-engineers snapshots into DDL
exports, schema diffs / migration SQL, DBML / Mermaid exports, and reversing
spec documents. Project owners can create read-only share links.

## Commercial-readiness bar

A buyer must be able to verify, from product-owned evidence, that: (1) schema
quality claims are backed by catalog or measured evidence, not heuristics;
(2) the deployment's isolation boundary is described accurately and enforced;
(3) large-schema behaviour has a published capacity envelope; (4) credential
lifecycle is auditable; (5) forward-engineering apply is governed with
rollback; (6) every release carries exact-head, migration, operability, and
supply-chain evidence.

## Commercial-readiness blocker (active incident)

**`ContextualWisdomLab/pg-erd-cloud` `main` has merged nothing since
2026-08-20.** Root cause: `ContextualWisdomLab/.github` GitHub Actions queue
saturation (`.github#1531`). The central required check `opencode-review`
dispatches a review to `.github` and polls ~90 min for a current-head
verdict; with ~800–900 runs queued org-wide the verdict does not arrive and
the check fails closed on every PR. A parallel remediation effort owns
`.github#1531`; a related `head_sha` TOCTOU in `opencode-review-dispatch.yml`
was found and is being addressed in that repo.

**Consequence for this baseline:** every gap increment below is shipped as a
small, tested, mypy-clean, 100%-docstring PR and **held merge-ready** until
the gate clears. As of iter22 the loop is holding **15 stacked increment
PRs** plus **this document** (PR #1040). Separately, PR #942 (the original
baseline draft) is green on every required check and waits only on one
non-author approval; it is not one of the 15 increments.

The 15 increments and the merge-wave order once the gate clears:

```text
#942  (approval-pending, not an increment)
  -> #1024 -> #1025
  -> #1031 -> #1032 -> #1033 -> #1035 -> #1048        (#947 chain)
  -> #1036 -> #1041 -> #1045                          (#951 chain)
  -> #1037 (#946)
  -> #1038 (#948) -> #1050
  -> #1039 (#950) -> #1049
  -> #1040 (this document)
```

## Status legend

| status | meaning |
| --- | --- |
| `spec'd` | issue defines the contract; no code yet |
| `in-progress` | ≥1 increment shipped as a merge-ready PR; more increments remain |
| `merge-ready-blocked` | code complete for this increment; waiting on the gate |
| `not-started` | no work this loop |

---

## #946 — Auditable credential-provider contract (`[Security/Product Gap]`)

**Feature spec (summary).** Replace unaudited runtime env/`.env` secret
transport with a provider-neutral `CredentialProvider` / `SecretReference`
boundary: bootstrap transport only, no plaintext in ORM rows / logs / traces /
metrics / repr; local mounted-file + org-registry + deterministic-test
providers; dual-read / single-write `APP_SECRET` rotation; fail-closed on
missing / revoked / expired / symlinked / oversized / malformed material;
recovery runbook proving key-unavailable recovery cannot expose DSN plaintext.

**Current state.** `Settings` builds directly from env / `.env`.
`APP_SECRET_FILE` is a fail-closed `/run/secrets` seam but every other
credential (DB, OIDC, LLM, Clearfolio HMAC, metrics, Valkey) is unmanaged
runtime config.

**Gap.** No single auditable credential lifecycle; no rotation; no access
attribution.

**This loop's increment PRs.**
- **#1037** — `app/secret_provider/`: typed `CredentialProvider` Protocol,
  `SecretReference` (no value), `ResolvedSecret` (value only via `reveal()`;
  `str`/`repr`/`format`/logs redact), fail-closed `SecretResolutionError`,
  `LocalMountedFileProvider` (fail-closed on missing/empty/oversized/non-UTF8/
  symlink/path-escape/non-file), `DeterministicTestProvider`. 14 tests incl.
  "value never appears in str/repr/format/logs". Rotation design documented.

**Remaining increments.** `Settings` integration behind a `local_secret_file`
profile; org credential-registry provider with cache-TTL + fail-closed
timeout/permission/revoked/stale; implement `APP_SECRET` dual-read rotation +
resumable re-encryption migration; key-recovery runbook; move LLM credentials
to `contextual-orchestrator`; persisted non-secret credential metadata.

**Status:** `in-progress`.

---

## #947 — Evidence-backed 3NF, FD, and hot-partition assessment (`[Product Gap]`)

**Feature spec (summary).** A versioned Schema Quality & Operability
Assessment: normalization / functional-dependency findings from catalog +
profiling + declared-rule evidence (never a theorem from column names), with
`observed` / `declared` / `inferred` / `proposed` / `waived` evidence classes,
source refs, caveats, next actions, and signed waivers; hot-partition & growth
findings from workload evidence or an explicit capacity profile, with
`EXPLAIN` pruning fixtures; report as JSON + accessible HTML table + buyer
summary.

**Current state.** `app.spec` has naming lint, wide-table, constraint, index,
FK-cycle analyzers. No normalization assessment; JSONB payloads are stored but
never described as 3NF proof.

**Gap.** No defensible normalization / hot-partition answer for a buyer.

**This loop's increment PRs.**
- **#1031** — `app/spec/normalization_assessment.py`: catalog-evidence
  analyzer. Findings: `non_atomic_column` (1NF), `missing_candidate_key`
  (BCNF → insufficient_evidence), `nullable_unique_determinant` (BCNF),
  `partial_dependency_precondition` (2NF). Evidence classes; waivers by scope.
  14 golden fixtures.
- **#1032** — `app/spec/normalization_report.py` + `GET
  /api/snapshots/{uuid}/normalization-assessment`: versioned report envelope
  (stable SHA-256 fingerprint, generated_at, summary headline). IDOR-safe.
- **#1033** — `app/spec/hot_partition_assessment.py` + `GET
  /api/snapshots/{uuid}/hot-partition-assessment`: catalog + optional explicit
  capacity profile. Findings: `append_heavy_table`, `unbounded_retention`,
  `monotonic_key_hot_page`, `partition_semantics_review`, `skew_candidate`.
  Concrete remediations only when a capacity profile supplies the quantity or
  the signal is catalog-declared. 10 fixtures.
- **#1035** — `app/spec/assessment_html.py` + `?format=html` on both
  endpoints: accessible exact-value HTML (every cell `html.escape`d;
  text-label state, not colour; `<table>` per finding kind). Completes the
  "JSON + HTML + summary" contract line.
- **#1048** — `app/spec/transitive_dependency_assessment.py`
  (`assess_transitive_dependencies`): the third-normal-form layer. From the
  catalog alone it can only flag `non_key_reference_cluster` — more than
  one non-candidate-key foreign-key column beside non-prime descriptive
  columns — as a *structural precondition* (evidence class `inferred`,
  with a caveat that profiling or a declared FD is needed). Given a
  caller-supplied `declared_functional_dependencies` list it asserts a real
  3NF violation as `transitive_dependency_via_declared_fd` (evidence class
  `declared`) and pairs it with a `candidate_3nf_split` proposal (evidence
  class `proposed`, never applied). It never infers a dependency from
  column names; unresolvable declared FDs are returned, not dropped.
  13 golden fixtures.

**Remaining increments.** Row-level functional-dependency *discovery* from
table data (a profiling service, out of scope for the pure analyzer);
persisted signed waiver records; the `EXPLAIN` pruning fixtures against a
real PostgreSQL; the versioned `assessment_run` persistence; a Rust core
once the #951 profile shows a measured hotspot.

**Status:** `in-progress`.

---

## #948 — Snapshot promotion, bitemporal lineage, retention, recovery (`[Product Gap]`)

**Feature spec (summary).** A first-class immutable lineage & promotion model:
separate `captured_at` / `available_at` / `valid_from` / `valid_to` /
`recorded_at` / `superseded_at` / `knowledge_cutoff`; typed parent→child
derivations (`captured_from` / `imported_from` / `normalized_from` /
`compared_with` / `exported_from` / `planned_from`); optimistic-concurrency
promotion that closes intervals rather than rewriting; `development` /
`staging` / `production` environments; retention & legal hold as policy
records, not background deletes; recovery restores metadata + a diagram state
only (never a live DB).

**Current state.** Immutable `schema_snapshot` / `schema_snapshot_data` +
`diff_snapshots`. A timestamped list, no lifecycle.

**Gap.** No approved-baseline record, no derivation typing, no retention
policy, no recovery checkpoint.

**This loop's increment PRs.**
- **#1038** — `app/lineage/`: pure model + algorithms (no DB). `lineage_model`
  bitemporal TypedDicts; `build_lineage_graph` (typed-edge DAG, cycle /
  self-loop / unknown-kind rejection, topo order, orphans / dangling
  reported); `apply_promotion` (append-only optimistic concurrency, closes
  prior interval, `PromotionConflictError`); `decide_retention` (disposition
  record, never deletes; promoted + legal-hold protected). 9 tests.
- **#1050** — `app/lineage/prov_projection.py` (`to_prov_document`): a pure
  W3C **PROV-JSON** projection of the `build_lineage_graph` result. One
  `prov:Entity` per snapshot id (including ids referenced only as a dangling
  parent); one `wasDerivedFrom` per typed edge, carrying `pg:derivationKind`
  so the "by kind" information survives. PROV-JSON is plain JSON, so no new
  dependency; deterministic and `json.dumps`-serializable. 9 tests.

**Remaining increments.** Normalized tables + Alembic migration; repositories
+ a `Settings`-gated HTTP surface (history / compare / promote / supersede /
archive / recover); a `wasGeneratedBy` / `activity` layer on the PROV
projection once the persisted model records the tool / commit / policy per
snapshot; embed exact references into every export.

**Status:** `in-progress`.

---

## #949 — Governed forward-engineering apply, rollback, recovery (`[Product Epic]`)

**Feature spec (summary).** The snapshot → DDL path must become a
protected, versioned vertical workflow: base snapshot → proposed target →
deterministic migration plan → risk/precondition review → isolated dry run
→ live read-only preflight → human approval → bounded apply → convergence
capture → success or recovery → immutable evidence bundle. The issue
mandates a **bounded-PR decomposition** rather than one growing branch:

1. **Plan authority & compiler** — immutable source/target snapshot IDs +
   hashes; deterministic typed operations with dependency order; a
   dialect/version capability matrix; reversible / conditionally reversible
   / irreversible classification; fixed resource limits; no free-form SQL
   authority.
2. **Sandbox runtime** — ephemeral isolated PostgreSQL 14–18 with no
   production credentials or customer network; CPU/memory/storage/
   wall-clock/statement/output bounds; cleanup + orphan reaper; a
   convergence report.
3. **Stored-target live preflight provider** — exact project / connection /
   base-snapshot / attempt-lease binding; post-connect revalidation;
   read-only catalog capture + precondition checks; DNS/SSRF/TLS + least
   privilege; secret-safe errors; cancellation.
4. **Approval & authorization** — deployer role + maker-checker for
   high-risk plans; exact plan digest / target fingerprint / environment /
   expiry / scope; approval invalidated on any plan/target/state change; an
   accessible review UI that explains risk and the next action.
5. **Apply worker** — production consumer registration; one active attempt
   per run with fenced leases + heartbeats; statement-level timeouts +
   cancellation checkpoints; a transaction boundary declared per operation
   class; retry only where idempotency is proved; no generic replay of
   partially committed DDL.
6. **Convergence & recovery** — recapture target state through the same
   guarded connection; compare actual vs planned; distinguish success /
   partial / divergent / unknown; generate recovery guidance from known
   committed operations; integrate approved backup/PITR evidence; never
   claim automatic rollback for irreversible or non-transactional DDL.
7. **Operations & evidence** — durable event/outbox/inbox; OpenTelemetry
   traces + metrics with no DSN/schema-value leakage; incident +
   cancellation runbooks; downloadable signed execution evidence +
   machine-readable provenance; recovery from restart / worker crash /
   lease loss / queue duplication / provider timeout.

**Safety invariants (must hold).** `dry_run=false` stays default-deny
until deployment policy explicitly enables the final apply capability; a
legacy free-form SQL route can never silently become structured apply
authority; the worker never accepts plaintext DSNs, connection overrides,
or plan SQL from queue payloads; every external identifier is re-resolved
and re-authorized at execution time; the target is sticky to the approved
provider/connection lineage; no status is `successful` before post-apply
convergence evidence is committed transactionally with the outbox event.

**Current state.** `app/ddl/apply_postgres_ddl` runs a validated
`ForwardDdlBatch` inside one transaction, `dry_run` default, SSRF-guarded.
`migration_safety.analyze_migration_safety` classifies risk. PR #834 built
an execution-neutral foundation (structured plans, dry-run attempts,
cancellation, leases, live preflight, audit evidence) but deliberately
registers no production consumer, provisions no sandbox, grants no live
apply authority, and proves no process recovery.

**Gap.** No production apply consumer; no sandbox runtime; no approval
record bound to an exact plan digest; no convergence/recovery step; no
immutable evidence bundle; #834's useful commits are not yet decomposed
onto protected `main`.

**This loop's increment PRs.** _none yet_ — deferred behind the #948
lineage model (parts 1 and 6 reuse `planned_from` / `exported_from` edges
and audit records) and the #946 credential boundary (part 3 preflight
provider). Sequencing #948 → #946 integration → #949 part 1 avoids
building the plan model twice.

**Remaining increments.** All seven parts above, each as a bounded PR from
protected `main` with exact-head evidence; realistic acceptance tests on
PostgreSQL 14–18 (additive column/index/FK, rename, type conversion,
partition op, extension-owned index AM, quoted multilingual identifiers)
and failure injection (lock contention, statement timeout, deadlock,
connection loss, worker `SIGKILL`, lease expiry, duplicate signal, restart;
plan/target changed after approval; partial-commit recovery without
replay).

**Status:** `spec'd` (foundations forming in #948 / #946; adjacent to #948
lineage).

---

## #950 — GA deployment profiles, tenant isolation, SSO, provisioning (`[Enterprise Gap]`)

**Feature spec (summary).** Two explicit, published profiles behind the same
contracts: `single_tenant_managed` (one org per deployment/database, external
OIDC / Keyverse with org binding, customer-owned backup/secret/network
policy, no cross-customer claim) and `multi_tenant_saas` (normalized tenant
authority tables; every persisted & cached object carries or derives an
immutable `tenant_account_uuid`; provisioning lifecycle with receipts;
per-tenant data-residency). Never imply multi-tenancy because projects have
members.

**Current state.** Project membership, OIDC verification, API keys, encrypted
DSNs, share links. No tenant authority; no isolation-mode contract.

**Gap.** No truthful deployment claim; no enforced tenant ownership.

**This loop's increment PRs.**
- **#1039** — `app/deploy/profile.py`: typed `DeploymentProfile` +
  `validate_profile()` honesty validator (rejects a dishonest GA claim for
  either profile), `AUTHORITY_BEARING_OBJECTS` enumeration,
  `PROFILE_A_TEMPLATE` / `PROFILE_B_TEMPLATE`. 9 tests.
- **#1049** — `app/deploy/tenant_authority_check.py` (`check_tenant_authority`):
  the concrete check behind the `all_authority_objects_tenant_scoped` bool.
  Given `{name, columns, derives_tenant_from}` table descriptions it
  partitions every `AUTHORITY_BEARING_OBJECTS` entry into `carrying` (has
  `tenant_account_uuid`) / `derived` (scoped through a named parent) /
  `missing_scoping` / `missing_definition`, and is `compliant` only when
  neither missing-list has an entry. `single_org_per_database` returns
  `applicable=False` / `compliant=True` with a reason. Pure; 11 tests.

**Remaining increments.** `tenant_account` authority tables + migration; a
repository layer deriving `tenant_account_uuid` on every authority-bearing
read/write, feeding the real ORM metadata to `check_tenant_authority`; SSO /
SCIM identity-link + provisioning flows; data-residency enforcement; a
`Settings`-selected active profile with a fail-closed startup self-check
running `validate_profile` and `check_tenant_authority`.

**Status:** `in-progress`.

---

## #951 — Large-schema SLOs, workload benchmarks, measured Rust boundary (`[Performance Gap]`)

**Feature spec (summary).** A versioned Performance & Capacity Profile:
deterministic anonymized `small` / `medium` / `large` workload generators plus
skew cases; measured paths (capture, hashing, JSON encode/decode + persist,
diff, export, API, queue, browser); p50/p95/p99 + RSS + allocations + query
count + lock wait + queue lag + artifact size + cancellation time; SLOs
separated from benchmark targets, **no SLA until production evidence**; a Rust
decision gate ADR per measured hotspot.

**Current state.** Focused perf work (background introspection, indexed queue
claims, bounded parsing, memoized search). No published capacity envelope.

**Gap.** No reproducible workload model, no measured baseline, no Rust
decision evidence.

**This loop's increment PRs.**
- **#1036** — `app/perf/workload_profiles.py`: deterministic anonymized
  generators hitting #951's exact counts for `small` / `medium` / `large`;
  skew builders (5,000-col relation, dense FK cluster, deep chain,
  disconnected components, multilingual/quoted identifiers + large comments,
  partition hierarchy). Seeded → byte-identical. **No invented threshold**
  (meta-test enforced). 12 tests; `large` in ~0.4s.
- **#1041** — `app/perf/baseline.py` (stacked on #1036):
  `run_baseline(profile_name, *, seed=None) -> dict` times the pure
  side-effect-free paths — canonical hash, JSON round-trip, self-diff,
  PostgreSQL + Snowflake DDL export, data-dictionary Markdown — and records
  only `wall_seconds`, `tracemalloc` `peak_bytes`, and `result_size_bytes`
  per path. `python -m app.perf.baseline --profile small [--seed N]
  [--json]` CLI. `tracemalloc` torn down in `finally`; a cancelled run
  returns no partial report. **No threshold or verdict** (meta-test
  enforced). 9 tests.
- **#1045** — `app/perf/baseline_stats.py` (stacked on #1041):
  `aggregate_baseline(profile_name, *, repeat, seed=None) -> dict` runs
  `run_baseline` `repeat` times over the *same* seeded workload (snapshot
  fixed; only timing varies) and reduces each path's `wall_seconds` and
  `peak_bytes` sample lists to `{samples, min, max, mean, p50, p95, p99}`
  via `statistics.quantiles` (standard library only). `result_size_bytes`
  is deterministic, so it stays a scalar. `repeat < 1` → `ValueError`;
  `repeat == 1` → degenerate summary; a cancelled run returns no partial
  aggregate. `python -m app.perf.baseline_stats --profile small --repeat 5
  [--seed N] [--json]` CLI. **No threshold or verdict** (meta-test
  enforced). 9 tests.

**Remaining increments.** The DB / event-loop paths (API
list/detail/pagination/search, queue claim/retry/lease/cleanup/fairness) in
the benchmark workflow; `docs/PERFORMANCE.md`; the release-candidate
benchmark workflow with a reproducibility receipt; frontend traces;
per-hotspot Rust decision-gate ADRs.

**Status:** `in-progress`.

---

## #952 — Tenant-scoped document & LLM workflows without weakening standalone (`[Ecosystem Gap]`)

**Feature spec (summary).** Turn the currently-optional connector calls
into three complete, governed vertical workflows while keeping standalone
operation fully functional:

1. **Reference-document attachment** — project/snapshot/table → authorized
   attachment intent → signed tenant/purpose request → Clearfolio
   conversion job → durable connector receipt → viewer artifact reference →
   project evidence drawer. Needs normalized `connector_account` /
   `connector_grant` / `document_reference` / `attachment_binding` /
   `connector_job` / `connector_receipt` metadata; opaque external IDs only;
   short-lived signed tenant/project/purpose claims; an allowlisted
   endpoint with exact host/port/method/MIME/timeout/size/redirect/retry
   policy; consent + data-classification review; status/retry/cancel/
   revoke/expiry; immutable source hash; no document contents in any log,
   metric, billing record, or LLM trace.
2. **Grounded reversing specification** — exact snapshot + authorized
   references → evidence bundle → orchestrator operation (e.g.
   `draft_database_reversing_spec`) → schema-bound draft → independent
   grounding verification → reviewed revision. Must send bounded semantic
   evidence units (never whole documents or DSNs); record snapshot hash,
   evidence IDs, model/provider IDs, prompt hash, orchestration mode,
   reasoning effort, knowledge cutoff, and verification result; distinguish
   local deterministic draft / LLM draft / verified draft / human-approved
   revision; detect unsupported claims, wrong object names / cardinality,
   inverted relationships, fabricated rationale, and prompt injection from
   comments or documents; no automatic publication or migration approval.
3. **Naruon / context-fabric projection** — a read-only versioned evidence
   contract for authorized consumers: canonical references, truth status
   (`observed` / `declared` / `inferred` / `proposed`), valid/system time +
   knowledge cutoff, provenance + source hashes, policy-filtered metadata
   with no DSN/secret, an idempotent event/receipt contract, and **no
   requirement that naruon be present** for standalone operation.

**Product boundary (explicit in the issue).** pg-erd-cloud stays the
authority for ERD projects, connections, snapshots, views, annotations,
sharing, migration plans/runs, and connector *references*. It does not
become a document viewer, object store, PIM/knowledge graph, or LLM
gateway. Clearfolio owns document conversion/viewer jobs; contextual-
orchestrator owns provider/model discovery, routing, fallback,
orchestration, evaluation, and cost/quality telemetry; naruon may consume
pg-erd-cloud evidence through an explicit connector but never owns project
state. Every integration is optional and fails as an *unavailable
capability*, not a broken core product.

**Current state.** `app/spec/llm.py` already performs a **configuration-
only** OpenAI-compatible integration: it calls a `/chat/completions`
endpoint via `LLM_API_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` (see
`docs/llm-orchestrator-integration.md`) and the local deterministic
reversing spec / data dictionary work with no LLM configured. The
transport works; what is missing is governance, not a connection.

**Gap.** The LLM credentials are unmanaged runtime config (ties to #946);
model discovery / capability routing / fallback / evaluation are not
delegated to `contextual-orchestrator` (the issue requires replacing
direct per-provider runtime authority with a versioned orchestrator
operation, and supporting non-chat-completions model classes such as
NVIDIA NIM via discovery + fallback); no tenant/purpose scoping or
evidence lineage on document artifacts (ties to #950); connector
failure / retry / revocation is not one coherent UI + audit contract; no
`standalone`-mode conformance test proving all connectors can be disabled.

**This loop's increment PRs.** _none yet_. Foundations are in PR #1037 (the
credential-provider boundary the orchestrator client sits behind) and in
PR #1039 (the tenant authority model the artifact scoping needs).

**Remaining increments.** A versioned `contextual-orchestrator` client
behind the #946 provider boundary that replaces the direct
`LLM_API_*` runtime authority and adds discovery / capability routing /
fallback / grounding verification; the normalized connector-reference
metadata + Clearfolio attachment workflow; tenant-scoping of
reversing-spec / data-dictionary / connector artifacts per #950; the
naruon read-only evidence contract; a `standalone` profile conformance
test (no network, no Keyverse, all connectors disabled) plus adversarial
tests (cross-tenant attachment, credential revocation mid-job, webhook
replay/reorder, DNS-rebind / oversized body / wrong MIME, document + schema
comment prompt injection, fabricated table/column/FK in LLM output,
knowledge-cutoff leakage).

**Status:** `spec'd` (transport exists; governance blocked on #946 + #950
foundations).

---

## #953 — First commercial release with exact-head, migration, operability, supply-chain evidence (`[Release Epic]`)

**Feature spec (summary).** Produce the first truthful, installable,
supportable **single-tenant managed / self-hosted GA candidate**.
Multi-tenant SaaS stays non-GA until #950 is complete; the release must
work standalone with optional CWL connectors as capability additions, not
hidden prerequisites. The epic **owns release integration only** and must
not duplicate implementation bodies. Its work:

- **PR-queue shaping.** Capture the exact protected-`main` SHA, ruleset,
  required checks, and every open PR's exact head. Classify each PR:
  unique in-scope change / stack dependency / superseded-duplicate /
  contaminated aggregate needing reconstruction / experiment-or-post-GA /
  blocked by the org control-plane incident. Close duplicates with a link
  to the canonical issue; never transfer stale-head review evidence.
  Rebase bounded stacks in dependency order without force-pushing over
  concurrent agent work. Refresh **this document** after each integration
  wave. A release-cut branch/tag comes only from protected `main`.
- **Dependency backlog** (each gets an explicit `release_blocker` /
  `post_ga_committed` / `experimental` / `not_planned` decision + rationale
  before release): #946, #947, #948, #949, #950, #951, #952, #865
  (orphaned Actions identities), #899 / #928 / PR #944 (design-system /
  Storybook contract), PR #936 / #838 (ORM ↔ Alembic exact-head drift).
  Core security, data integrity, migration safety, standalone deployment,
  backup/restore, operability, licensing, and supported-database
  truthfulness cannot be deferred silently.
- **Required release evidence.** A clean-environment browser/API rehearsal
  of the full product journey (login → project → encrypted connection →
  async snapshot → ERD search/layout/annotation/saved view → diff/exports →
  share + revocation → approved snapshot/history → backup and restore);
  clean install on PostgreSQL 18 + the compatibility matrix; upgrade from
  the oldest supported `0.1.x` through every Alembic revision +
  downgrade/rollback policy; ORM↔migration drift producing no unreviewed
  DDL; backup + PITR/logical restore + queue/job recovery after restart;
  100% production statement + branch + public-API docstring coverage with
  real PostgreSQL fixtures; fuzz/property tests at the DSN / identifier /
  snapshot / DBML-DDL / import-export / connector boundaries; threat model
  + secure deployment guide + a CSAP / SOC 2 control **crosswalk** (an
  engineering evidence map, not a certification claim); reproducible
  backend/frontend/container builds; an SPDX or CycloneDX **SBOM** per
  artifact; **SLSA v1.2**-compatible build provenance; container + FS vuln
  results with reviewed exceptions; a signed tag/release + documented
  rollback; an **immutable release manifest** (source commit, migrations,
  dependency locks, workflow provenance, SBOM, image digest, test/benchmark
  receipts, Figma file ID, known limitations); liveness/readiness split;
  OpenTelemetry traces/metrics/logs with stable cardinality and no
  secrets/customer values; SLI/SLO + capacity profile linked to #951;
  dashboards/alerts + runbooks for secret loss/rotation, target outage,
  queue backlog, failed migration, backup restore, dependency incident,
  compromised share/API key.

**Current state.** At `main@8dc74692` backend + frontend versions are
`0.1.0`; the repo has 60+ open PRs. Supply-chain pinning is already
enforced (hash-locked pip, digest-pinned Docker, SHA-pinned Actions,
OpenSSF Scorecard). CI runs mypy + pytest + typecheck + vitest + production
build + CodeQL + Scorecard + dependency-review. No tagged,
provenance-backed release candidate proves the complete buyer journey; no
consolidated release-evidence manifest exists.

**Gap.** No single release-evidence manifest; no PR-queue classification of
record; the operability baseline (#951), tenant claim (#950), credential
lifecycle (#946), lineage (#948), and governed apply (#949) are all
incomplete; PR #834's useful commits are not yet decomposed onto `main`.

**This loop's increment PRs.**
- **#1040** — this document: the first artifact toward the #953 evidence
  manifest. It currently classifies only **this loop's own increment
  PRs** (each mapped to its issue, with the org-incident blocker named and
  the merge-wave dependency order stated). The full #953 PR-queue shaping
  step — every one of the ~60 open PRs captured at its exact head and
  classified as unique / stack-dependency / superseded-duplicate /
  contaminated-aggregate / experiment-or-post-GA / blocked-by-incident —
  is **not yet done** and remains a tracked #953 deliverable (see
  "Remaining increments").
- **#1024** — `.Jules` ↔ `.jules` case-collision fix that unblocks
  CI-clean git operations on case-insensitive filesystems (release-hygiene
  prerequisite for any rebase wave).
- **#1025** — local Playwright E2E harness + `nanoid` pin (closes #1014);
  the harness the product-journey rehearsal will extend.

**Remaining increments.** The full open-PR classification table (every
open PR at its exact head, with a `release_blocker` / `post_ga_committed`
/ `experimental` / `not_planned` decision + rationale) — deferred until
the incident clears and the merge wave drains the loop's own stack, since
classifying ~60 PRs that cannot merge yet would go stale immediately; a
release-evidence manifest generator; the operability baseline; migration
rehearsal automation; then a synchronized version bump + `CHANGELOG`
release section + `RELEASE_NOTES.md` once #946–#952 reach `merge-ready` on
their MVP increments.

**Status:** `spec'd` (this document + #1024 / #1025 are the first
release-hygiene increments).

---

## Cross-repo / ecosystem

| repo | relationship to pg-erd-cloud | status |
| --- | --- | --- |
| `ContextualWisdomLab/.github` | Central required-workflow authority (`opencode-review`, `strix`, coverage, scorecard). **Currently the commercial-readiness blocker** (`#1531`). | incident, owned by a parallel effort |
| `ContextualWisdomLab/keyverse` | Central Identity Provider — the `keyverse` identity mode in #950; org binding for the single-tenant GA profile. | not yet integrated |
| `ContextualWisdomLab/contextual-orchestrator` | The LLM access contract #946 §9 and #952 require pg-erd-cloud to adopt instead of a per-provider key. | not yet integrated |
| `ContextualWisdomLab/wardnet` | Rust-first gateway / SOC control-plane baseline; relevant to #950 ingress + #953 operability. | not yet integrated |
| `ContextualWisdomLab/TEPP`, `fast-mlsirm` | Psychometrics platforms — **not consumed by pg-erd-cloud**; listed for ecosystem completeness only. | n/a |
| `ContextualWisdomLab/RankWeave`, `ThreadWeave`, `LineageWeave`, `disksage` | Independent libraries; `LineageWeave`'s DAG-reconstruction idea informed the #948 lineage model shape but the code is not imported. | n/a |

## References (APA 7th)

The contracts summarized above lean on these external standards; each gap's
own doctoring note under `docs/doctoring/` carries the domain-specific
citations for its increment.

- American Educational Research Association, American Psychological
  Association, & National Council on Measurement in Education. (2014).
  *Standards for educational and psychological testing*. American
  Educational Research Association.
  https://www.aera.net/Publications/Books/Standards-for-Educational-Psychological-Testing-2014-Edition
  — evidence-class framing (`observed` / `declared` / `inferred` /
  `proposed`) in #947, #948, #952.
- Codd, E. F. (1970). A relational model of data for large shared data
  banks. *Communications of the ACM, 13*(6), 377–387.
  https://doi.org/10.1145/362384.362685 — the relational-normalization
  basis (further normal forms follow in Codd, 1971/1972); normalization
  assessment in #947.
- International Organization for Standardization. (2017). *Health
  informatics — Pseudonymization* (ISO/TS 25237:2017).
  https://www.iso.org/standard/63553.html — cited for the principle that
  protection is access control, encryption, purpose limitation, and audit
  rather than blanket masking; the non-masking protection stance in #946,
  #949, #953.
- National Institute of Standards and Technology. (2022). *Secure software
  development framework (SSDF) version 1.1* (NIST Special Publication
  800-218). https://doi.org/10.6028/NIST.SP.800-218 — the release evidence
  and governed-apply controls in #949 and #953.
- PostgreSQL Global Development Group. (2026). *PostgreSQL 18 documentation:
  Data definition*. https://www.postgresql.org/docs/18/ddl.html — the
  supported-operation matrix in #949 and the compatibility matrix in #953.
- SLSA Community. (2025). *Supply-chain levels for software artifacts
  specification, version 1.2*. https://slsa.dev/spec/v1.2/ — the build
  provenance and attestation requirements in #953.

## How this document is maintained

The autonomous review/merge loop updates this file each time a gap increment
ships or the incident status changes. This revision (iter22) added PR #1049
(the tenant-authority column-presence check) to the #950 list and PR #1050
(the lineage PROV-JSON projection) to the #948 list, taking the stacked-PR
count to 15. iter20 added PR #1048 (transitive-dependency / 3NF assessment)
to the #947 list. iter19 fixed the markdownlint MD018 line-start warnings
and the reference links flagged on PR #1040. iter18 added PR #1045
(repeat-run percentile aggregation) to the performance-gap increment list.
iter16 filled the three epic sections (#949, #952, #953) from their issue
bodies and aligned the LLM-orchestrator wording with the existing
configuration-only `/chat/completions` integration in
`docs/llm-orchestrator-integration.md`.
When the gate clears and PR #942 merges, reconcile its
`docs/product-technical-gap-baseline.md`,
`docs/doctoring/product-technical-gap-baseline.md`, and
`docs/adr/0002-product-technical-gap-baseline.md` with this consolidation.
