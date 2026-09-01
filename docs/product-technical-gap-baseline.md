# Product & technical gap baseline

**Last consolidated:** 2026-09-01 (autonomous review/merge loop, iter14).

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
the gate clears. As of iter14 the loop has 10 such PRs stacked
(#942, #1024, #1025, #1031, #1032, #1033, #1035, #1036, #1037, #1038, #1039).

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

**Remaining increments.** 3NF / transitive-dependency detection (needs
profiling or declared FDs); persisted signed waiver records; the `EXPLAIN`
pruning fixtures against a real PostgreSQL; the versioned `assessment_run`
persistence; a Rust core once the #951 profile shows a measured hotspot.

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

**Remaining increments.** Normalized tables + Alembic migration; repositories
+ a `Settings`-gated HTTP surface (history / compare / promote / supersede /
archive / recover); PROV-JSON-LD projection; embed exact references into every
export.

**Status:** `in-progress`.

---

## #949 — Governed forward-engineering apply, rollback, recovery (`[Product Epic]`)

**Feature spec (summary, from title — full re-read pending).** The
snapshot → DDL apply path must become *governed*: an approval gate before a
non-dry-run apply, a recorded plan / run / outcome, a rollback path, and a
recovery workflow distinct from metadata recovery.

**Current state.** `app/ddl/apply_postgres_ddl` runs a validated
`ForwardDdlBatch` inside one transaction, `dry_run` default, SSRF-guarded.
`migration_safety.analyze_migration_safety` classifies risk. No approval
record, no run history, no rollback beyond the single-transaction rollback.

**Gap.** No governance record, no multi-statement rollback strategy, no
recovery workflow.

**This loop's increment PRs.** _none yet._

**Remaining increments.** A `migration_plan` / `migration_run` model (can
reuse the #948 lineage `planned_from` / `exported_from` edges and audit
records); an approval gate; a `pg_dump`-anchored recovery-point contract;
apply-time safety re-check against the live target.

**Status:** `not-started` (adjacent to #948 lineage).

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

**Remaining increments.** `tenant_account` authority tables + migration; a
repository layer deriving `tenant_account_uuid` on every authority-bearing
read/write + a test that no authority table lacks the column; SSO / SCIM
identity-link + provisioning flows; data-residency enforcement; a
`Settings`-selected active profile with a fail-closed startup self-check
running `validate_profile`.

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

**Remaining increments.** A `run_baseline(profile, paths) -> dict` measurement
harness (plumbing only, no thresholds); `docs/PERFORMANCE.md`; the
release-candidate benchmark workflow with a reproducibility receipt; frontend
traces; per-hotspot Rust decision-gate ADRs.

**Status:** `in-progress`.

---

## #952 — Tenant-scoped document & LLM workflows without weakening standalone (`[Ecosystem Gap]`)

**Feature spec (summary, from title — full re-read pending).** The reversing
spec / data-dictionary / document workflows and the LLM draft path must be
tenant-scoped in the `multi_tenant_saas` profile while the `standalone`
profile keeps working with no network and no Keyverse. LLM access goes
through the `contextual-orchestrator` contract, not a per-provider key vault.

**Current state.** `app/spec/llm.py` calls an OpenAI-compatible provider
directly via `LLM_API_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`; local-only
reversing spec works without it. No tenant scoping on document artifacts.

**Gap.** LLM credentials are unmanaged (ties to #946); document artifacts are
not tenant-scoped (ties to #950); no `contextual-orchestrator` connector.

**This loop's increment PRs.** _none yet_ (foundations in #1037 credential
boundary and #1039 tenant authority model).

**Remaining increments.** A `contextual-orchestrator` client behind the #946
provider boundary; tenant-scoping of reversing-spec / data-dictionary /
connector artifacts per #950; a `standalone` profile conformance test
(no network, no Keyverse).

**Status:** `not-started` (blocked on #946 + #950 foundations).

---

## #953 — First commercial release with exact-head, migration, operability, supply-chain evidence (`[Release Epic]`)

**Feature spec (summary, from title — full re-read pending).** The umbrella
release gate: exact-current-head evidence for every claim, a rehearsed
migration path, an operability baseline (SLOs, dashboards, runbooks), and
supply-chain evidence (hash-locked deps, digest-pinned images, SBOM,
attestation). Consumes #946–#952.

**Current state.** Supply-chain pinning is already enforced (hash-locked pip,
digest-pinned Docker, SHA-pinned Actions, OpenSSF Scorecard). CI runs mypy +
pytest + typecheck + vitest + production build + CodeQL + Scorecard +
dependency-review. No consolidated release evidence manifest.

**Gap.** No single release-evidence manifest; the operability baseline
(#951), tenant claim (#950), credential lifecycle (#946), lineage (#948), and
governed apply (#949) are all incomplete.

**This loop's increment PRs.** This document is the first artifact toward the
#953 evidence manifest. Loop PRs #1024 (`.Jules` case-collision fix that
unblocks CI-clean git ops) and #1025 (local Playwright E2E harness + `nanoid`
pin, closes #1014) are release-hygiene prerequisites.

**Remaining increments.** A release-evidence manifest generator; the
operability baseline; migration rehearsal automation; then a version bump +
`CHANGELOG` release section once #946–#952 reach `merge-ready` on their MVP
increments.

**Status:** `spec'd`.

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

## How this document is maintained

The autonomous review/merge loop updates this file each time a gap increment
ships or the incident status changes. When the gate clears and PR #942
merges, reconcile its `docs/product-technical-gap-baseline.md`,
`docs/doctoring/product-technical-gap-baseline.md`, and
`docs/adr/0002-product-technical-gap-baseline.md` with this consolidation.
