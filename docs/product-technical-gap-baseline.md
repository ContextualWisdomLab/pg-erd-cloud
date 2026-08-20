# Product and technical gap baseline

- **Snapshot date:** 2026-08-21
- **Repository:** `ContextualWisdomLab/pg-erd-cloud`
- **Protected-main evidence:** `8dc746920c12988f082e914879d95e13c9693535`
- **Open-PR evidence:** GitHub REST query returned **62** open pull requests; exact heads remain mutable.
- **Package evidence:** backend and frontend both declare version `0.1.0`.
- **Status:** broad pre-GA product; no commercial release candidate is proven by this document.
- **Purpose:** convert product, architecture, research, issue, PR, review, check, migration, design, and operability evidence into one executable completion backlog.

## Product boundary

pg-erd-cloud is a standalone PostgreSQL-focused ERD collaboration product. It accepts an authorized database connection, creates immutable schema snapshots asynchronously, renders and edits an ERD, stores project-scoped views and annotations, computes diffs and migration-risk evidence, and exports DDL, DBML, Mermaid, Prisma, data dictionaries, and reversing specifications.

It must remain independently runnable and consumable as a module by the CWL ecosystem. Authority is split deliberately:

- pg-erd-cloud owns ERD projects, membership, encrypted connection metadata, snapshots, views, annotations, sharing, API keys, migration-plan/run metadata, and its PostgreSQL job queue;
- `keyverse` or an external issuer owns identity and lifecycle provisioning;
- `clearfolio` owns document conversion and viewing;
- `contextual-orchestrator` owns model discovery, routing, fallback, orchestration, and LLM evaluation;
- `naruon` owns its PIM/knowledge-graph control plane and may consume explicit pg-erd-cloud evidence contracts;
- central `.github` owns reusable review, security, Strix, Noema, and merge-governance workflows.

The product must not silently become a general-purpose graph database, document viewer, identity provider, object store, or LLM gateway.

## Initial GA claim boundary

The first defensible release target is **`single_tenant_managed`**: one customer organization per deployment/database, project RBAC, OIDC organization binding, customer-controlled network/secrets/backup policy, and no cross-customer SaaS claim.

`multi_tenant_saas` is non-GA until issue #950 proves tenant authority on every persisted, queued, cached, exported, and connector object; database-enforced isolation; identity provisioning/deprovisioning; tenant-scoped encryption; backup/restore; residency; and adversarial cross-tenant tests.

Forward-engineering persistent apply is also non-GA until issue #949 closes. DDL export and execution-neutral planning may ship earlier only when the release notes state that persistent apply remains disabled.

## Current evidence map

| Area | Current evidence | What it proves | What remains unproved |
|---|---|---|---|
| Backend | `backend/app/api/`, `backend/app/pg_introspect/`, `backend/app/ddl/`, `backend/app/diff/`, `backend/app/spec/` | A broad standalone API and schema-analysis surface exists | Complete buyer E2E, support matrix, SLOs, and safe live apply |
| Persistence | `backend/app/models.py`, Alembic revisions, PR #936 and #838 | Core metadata is relational and migration drift is being addressed | Clean upgrade/downgrade evidence, full 3NF assessment, hot-partition plan |
| Background work | `backend/app/jobs/worker.py`, `job_queue`, `FOR UPDATE SKIP LOCKED`, optional Valkey wake-up | Long-running snapshot work is separated from HTTP requests | Fairness, partition rollover, back-pressure, restart/region recovery, large-schema capacity |
| Security | encrypted DSNs, target guards, OIDC/JWT work, API keys, CSRF/CORS/share controls | Multiple concrete trust boundaries exist | Auditable runtime secret authority, rotation/re-encryption, complete tenant claim, release security evidence |
| Frontend | React/Vite/React Flow, Vitest tests, PR #944 Storybook/token inventory | Core canvas, navigation, exports, accessibility, polling, and visual-token work are testable | Protected-main Storybook/browser E2E, full repeated-component inventory, large-graph virtualization |
| Forward engineering | exports/diffs plus the large execution-neutral stack in PR #834 | A sophisticated plan/dry-run/recovery foundation is being built | Bounded production consumer, sandbox lifecycle, approval, apply, convergence, recovery |
| Snapshot lifecycle | immutable payload and timestamped snapshots | Captures can be retained and compared | Promotion, valid/system time, derivation lineage, retention, legal hold, recovery workflow |
| Ecosystem | connector documentation and active LLM/Clearfolio work | Optional integration intent is explicit | Durable tenant/purpose contracts, failure UX, grounded verification, standalone contract tests |
| Design | live Figma files, `docs/ui-ux/`, PR #944, issues #899/#928 | Reviewed visual intent and a component-contract path exist | Merged Figma ↔ token ↔ Storybook ↔ production traceability |
| Governance | protected main, central ruleset, required checks, PR #943, issue #865 | Exact-head review/security/merge policy is explicit | A release-shaped queue and a reconciled Actions registry |
| Packaging | backend/frontend `0.1.0`, Docker/Compose profiles | Installable development and production-style profiles exist | Signed release, SBOM, provenance, reproducible artifacts, backup/restore rehearsal |

## Definition of product completion

A release may be called complete only when every applicable gate has immutable evidence, not merely a document or an old successful check.

| Gate | Required evidence |
|---|---|
| Buyer journey | Clean login → project → authorized connection → async snapshot → ERD work → diff/export → share/revoke → history → backup/restore browser/API E2E |
| Data integrity | ORM/migration parity, clean install/upgrade rehearsal, encrypted-DSN recovery, queue recovery, deterministic snapshot/export contracts |
| Security | Threat model, OIDC/JWT/CSRF/CORS/API-key/share/SSRF/TLS/secret tests, purpose/access controls, incident and rotation runbooks |
| Quality | Production statement and branch coverage 100%, public API/docstring coverage 100%, real PostgreSQL integration, property/fuzz and accessibility/i18n/UI action tests |
| Operability | Readiness/liveness, OpenTelemetry, SLI/SLO, dashboards, alerting, capacity, backup/restore, rollback/compensation, support matrix |
| UX/design | Figma authority, design tokens, Storybook inventory, keyboard/focus/zoom/forced-colors/reduced-motion, exact-value alternatives for graphs |
| Supply chain | Reproducible artifacts, dependency/action policy, SPDX/CycloneDX SBOM, SLSA v1.2 provenance, image digest, license notices, signed tag |
| Commercial truth | Versioned GA/beta/experimental claims, known limits, release notes, upgrade policy, security/support contacts, no unproved multi-tenant/apply claim |
| Ecosystem | Optional signed/versioned connectors with tenant/purpose/provenance/failure contracts; core product remains usable with every connector disabled |

## Executable gap and issue map

| Priority | Canonical issue/PR | Buyer-visible gap | Closure boundary |
|---|---|---|---|
| P0 | #953 | No coherent commercial release candidate across 62 open PRs | Exact-head release shaping, product/migration/backup/security/accessibility/operability evidence, version/tag/SBOM/provenance |
| P0 | #949 and PR #834 | Forward engineering stops before production apply authority and recovery | Decomposed plan → sandbox → preflight → approval → apply → convergence → recovery stack; persistent apply stays default-deny until complete |
| P0 | PR #936 / #838 | ORM and Alembic metadata can drift | Real PostgreSQL clean install, upgrade/downgrade rehearsal, deterministic no-drift contract, dependency order |
| P0 | #946 | Runtime configuration lacks one auditable secret lifecycle | Bootstrap-only transport, credential-provider contract, rotation/revocation, DSN re-encryption, standalone file provider |
| P0 | #950 | Project membership is not proof of multi-tenant SaaS isolation | Explicit single-tenant GA profile; database-enforced tenant authority before any SaaS claim |
| P0 | central `.github` #1153; target PRs #724/#745 | Bounded Strix context can create false or incomplete evidence | Merge canonical central repair, refresh immutable workflow pin, rerun affected exact heads |
| P1 | #948 | Snapshot timestamps/diffs are not a lifecycle | Bitemporal promotion, typed lineage, retention/legal hold, metadata recovery, provenance export |
| P1 | #947 | Schema quality is advisory and no hot-partition contract exists | Evidence-classified dependency/normalization assessment, waivers, workload-backed partition candidates |
| P1 | #951 | No enterprise capacity envelope or measured Rust boundary | Reproducible large-schema profiles, SLO/SLI, browser/backend traces, Rust only for proven hotspots |
| P1 | #952 | Clearfolio/contextual-orchestrator/naruon are not complete buyer workflows | Tenant/purpose-scoped durable connector receipts, grounded LLM verification, failure/retry/revocation UX, standalone fallback |
| P1 | PR #944, issues #899/#928 | Repeated web controls lack a merged executable design-system contract | Shared tokens, Storybook states, CSS/interaction/accessibility tests, Figma mapping |
| P1 | #865 | GitHub Actions registry advertises orphaned active workflow identities | Exact-main audit, safe disablement, immutable before/after ledger, central prevention |
| P2 | doctoring file and all issues above | Research and standards traceability is incomplete | APA 7 mapping from requirement → owner → contract → test → limitation; licensed artifacts are not copied unlawfully |

## Dependency order

```mermaid
flowchart TD
  Baseline[PR #942 baseline] --> Release[Issue #953 release epic]
  Scheduler[PR #943 protected hourly loop] --> Release
  Strix[Central .github #1153] --> Queue[Exact-head PR queue]
  Queue --> Release
  Drift[PR #936 / #838 migration parity] --> Release
  Secrets[Issue #946 credential authority] --> Release
  Tenant[Issue #950 GA deployment profile] --> Release
  Design[PR #944 + #899/#928 design contract] --> Release
  Forward[Issue #949 bounded forward engineering] --> Release
  Lineage[Issue #948 snapshot lifecycle] --> Release
  Quality[Issue #947 schema quality] --> Release
  Scale[Issue #951 SLO and Rust decision] --> Release
  Connectors[Issue #952 optional ecosystem workflows] --> Release
```

Not every P1 item must block the first `single_tenant_managed` GA. Issue #953 must classify each item as `release_blocker`, `post_ga_committed`, `experimental`, or `not_planned`, with buyer-facing rationale. Core data integrity, secret safety, truthful deployment scope, backup/restore, operability, and release provenance cannot be deferred silently.

## Design authority

The visual source of intent is recorded in ADR-0002:

- **Figma File ID:** `csnpEEJfmqFWB0vNUoTkWA`
- **Supplemental Figma File ID:** `OTN0rBGtnVy0P7yq4Iv9Si`

Figma does not replace executable behavior. Storybook stories, shared tokens, component/accessibility tests, browser interaction tests, and production code are the executable contract. Screenshots are QA evidence only. Figma, Storybook, product requirements, implementation, tests, current PRs, and review findings must have explicit traceability.

## Current open PR inventory

The live REST query returned **62** open pull requests on 2026-08-21. Exact heads are mutable; refetch after every push. PR #942 is self-referential and records its own current head like every other PR.

| PR | Exact head | Current purpose |
|---:|---|---|
| 954 | `ec0ab84b72e0acd0970abf9817a8f7b59f451dc6` | 🎨 Palette: 닫기 버튼 시각적 심볼 개선 (X -> ✕) |
| 944 | `5bbf2ee5b6efe9d15a99d7d4330fccb21e84e168` | feat(frontend): add Storybook design-token inventory |
| 943 | `a968d54daf1ddd663b801628a7817f4c5bf459ba` | ci: schedule hourly PR review repair |
| 942 | `153451e35cb5fc10ba71ec8d9dc7fb14ada1c1ce` | docs: establish product and technical gap baseline |
| 941 | `ac16049ab74c3ed3b6687598b77b2f0d6911053c` | fix(auth): offload API key hashing |
| 940 | `6cb7f19c84fd8511cb990b7b3f2298a0a90a2abc` | refactor(snowflake): group constraint context |
| 939 | `c41249160f54d263f45f32bf9e22cc0add5a3ec0` | fix(frontend): validate ERD export handles |
| 938 | `3f2e58989ea9e4a648bb7fbb3041a713ae890129` | refactor(mysql): group introspection rows |
| 936 | `5e73610f345535ce19f993561b728cfeb54f92e0` | fix(db): reconcile ORM metadata with migrations |
| 933 | `66005468dca31f51c0a3eed96bfdfd998ce25d71` | feat: add automatic column mapping and default fk label on edge creation |
| 930 | `cc66e5945944c00d6a9531912b59f0b3aaaebbf8` | 🎨 Palette: Add visual indicators for required form fields in modals |
| 926 | `ddb21e05880b8fc5f32b9ccedd54b74c81df3de1` | 🛡️ Sentinel: [MEDIUM] Fix control character injection in Pydantic schemas |
| 915 | `e006cef6f4949126450f2877d64040e7787fb7ae` | 🎨 Palette: [테이블 삭제 시 확인창 추가] |
| 914 | `df336c0dec6177b5c67299591c789dcbdb555a33` | chore(deps): bump github/codeql-action/analyze from 4.36.2 to 4.37.7 |
| 913 | `a8d01fc46f0e4114fcb47d8967703faa9319678c` | chore(deps): bump github/codeql-action/init from 4.36.2 to 4.37.7 |
| 912 | `6db324ac336a294b520dc05faffd176d8768ba23` | chore(deps): bump github/codeql-action/autobuild from 4.36.2 to 4.37.7 |
| 910 | `10b86e5a6a82e5c3d223960c3e10cafdff93be5e` | chore(deps-dev): bump @testing-library/jest-dom from 6.9.1 to 7.0.1 in /frontend |
| 909 | `7c3c5a584dff98dcd7e899f1dbd382afcb2b9a6a` | chore(deps-dev): update snowflake-connector-python requirement from <5,>=4 to >=4.7.2,<5 in /backend |
| 907 | `22dd0142e3c91589b754094466a947c4d28332e7` | chore(deps-dev): update setuptools requirement from >=82.0.1 to >=84.0.0 in /backend |
| 906 | `c87982f914552e584c51e115181d5b40aee599db` | chore(deps): update sqlalchemy requirement from <2.1,>=2.0.51 to >=2.0.52,<2.1 in /backend |
| 905 | `c761cc5b16e667f6c40f92f649471d8c0d109d79` | chore(deps): update starlette requirement from >=1.1.0 to >=1.6.0 in /backend |
| 904 | `1cfde61b4955b949668881e789a6d597fa9787d4` | chore(deps): bump python from 3.14.6-slim to 3.14.7-slim in /backend |
| 903 | `3c7a574799bf7e6a3b5a6ee8a1066eaba15c87e1` | feat(prisma): allocate collision-free identifiers with @map |
| 902 | `aa58625123766bfc46228f70efbd51cfa38ac7e5` | chore(opencode): use NVIDIA NIM only |
| 901 | `962f8299650dbd4f6f67703159dbf5e46c268a82` | fix(a11y): restore business-group color radiogroup contract |
| 900 | `b688317cfdaed848a75a3eeb8c1a10b15ae7f80e` | feat(ai): delegate LLM drafts to adaptive orchestration |
| 895 | `f0e474e28844588a1fc56c76ace411ab58a51491` | security(auth): reject unsupported JWT critical headers |
| 894 | `b0c511c3ef0f1cbe69619efd263152dcd4bb3665` | perf(prisma): index outgoing relation lookup |
| 890 | `3ba23838e71f7fd1768ae76f2b25db77a8a85e77` | test(api): verify the authenticated project-list contract |
| 889 | `8fbe9e814674bebeb85de8ea31485fc566e00f44` | security(ci): harden manual CodeQL backfill inputs |
| 888 | `7d4358396e1bc59a48c139535d80dab6a89935a2` | test(valkey): verify sentinel host formatting contracts |
| 887 | `a80bacc242bca71aa2fd060eacdde988c55a84f8` | fix(security): reject log-breaking identifier characters |
| 886 | `514281bf7ac66a4c902b7155eec9497a78c273b3` | test(api): verify the current-user HTTP contract |
| 884 | `e9585668f1284b0ff6e751a1bbd77f40853084f0` | perf(frontend): remove intermediate ERD handle-ID array |
| 882 | `c30af0eec1efeaf3364924548004bdcd0b040e96` | 🎨 Palette: 모달 내 일반 액션 버튼에 컨텍스트 ARIA label 추가 |
| 881 | `5a8ce593bc8b94c89c4cab0b9af36784a0dd472a` | perf(search): memoize immutable ERD searchable text |
| 874 | `1d3624213aa06761eaae961312499ebf565d784e` | fix: preserve DBML index evidence |
| 868 | `87672958270712cc8df00f9d2c79f9063bebf6b0` | security(postgres): reject server-local file access via DSNs |
| 858 | `a34b35e59bf76d8b311be041e040f0f1148b63e3` | a11y(frontend): keep unavailable toolbar actions discoverable |
| 857 | `fea40e0406fdc15339e9ecb9ace12234901350c5` | feat(databricks): add bounded Unity Catalog introspection |
| 856 | `322d543386c2658e563ae383780847f51f767fb9` | feat(frontend): add relationship-aware ERD layout |
| 855 | `b94eb617708782ccda5e5a3c199c749fbbf32a80` | fix(auth): bind OIDC tokens to configured organization |
| 850 | `682f107782bd7a9d5b5605de7d78402dc71cdd21` | ⚡ Bolt: Optimize ERD column name resolution |
| 838 | `5761ba6106fb8396bb511f3238c1ec6c21d6e13e` | chore(deps): update alembic requirement from >=1.18.5 to >=1.19.1 in /backend |
| 835 | `423564054a82e4158219cf56a9348652265e12da` | fix(a11y): use native form submission paths |
| 834 | `07a4e376ba0ed1ae2fead9892ba66f4b54b14c8d` | feat: establish forward engineering plan authority |
| 832 | `f385d337838a8304a2efb0ce9a2a4575280bae84` | security(api): reject non-text controls in multiline SQL |
| 827 | `137f715566a179c3b4f2c02b6b2957b5acc332f0` | ⚡ Bolt: [concurrent pooler detection] |
| 824 | `e34f69c2099d0e37cd04efe5b974515d0678476d` | feat: align live Figma, harden sharing, and establish architecture authority |
| 782 | `d70985baa0355e71845096529f8a8ea99ca7cba7` | fix(naming): classify PostgreSQL SYSTEM_USER as reserved |
| 774 | `9e14c0ddf6e8f7afadb2f0fcdcab9cff956ca66f` | fix(erd): preserve PostgreSQL identifiers in relationship inference |
| 772 | `fa121caed956b7e20bf1dafd199322944fd04e70` | chore(backend): remove dead relationship-inference lookup |
| 768 | `03d637684658ed4f501ef7a0c9d7a101b5123e40` | test(data-dictionary): cover missing-column rendering |
| 745 | `7c8afef1fde51e6c5086aa342f008f7aadbf4796` | 🛡️ Sentinel: [CRITICAL] Fix incomplete DSN secret redaction and over-redaction |
| 744 | `409343ce286f49b5a700200b6cca1a5d7e159f0c` | fix(cors): allow every supported API method |
| 738 | `43d594c9d955b273875c3234c02333439a819878` | test(frontend): await diagram data before search assertion (deflake main) |
| 737 | `8e58fc0867ab909d427724064daefa1397bac48e` | docs: align ecosystem names and solo-maintainer review policy |
| 725 | `203dce1b0ad4e79e709ce0c796c457d065db4fae` | chore(deps): synchronize FastAPI and Redis backend locks |
| 724 | `dbc315867013fbf0481853039ec53d75e6101743` | feat: add trusted local PostgreSQL snapshot CLI |
| 723 | `7c0457ab833b591d056261913a13a6b729c8e6e2` | feat(diagram-views): complete saved-layout update contract |
| 704 | `5f10da2a4bf4b4db93762281a5886650b74887a3` | a11y(frontend): expose unavailable table-save state to keyboard users |
| 698 | `00eb7938217eeae51ed12c7188c85b36e5414174` | a11y(frontend): keep unavailable export actions discoverable |


1. Refetch protected `main`, the ruleset, and required contexts.
2. Refetch every PR exact head, mergeability, draft state, review submissions, unresolved threads, and all check runs.
3. Classify source-actionable failures separately from provider queue/limit/control-plane failures.
4. Repair only the current head. Do not transfer approval or check evidence from a predecessor SHA.
5. Run focused tests, then the full proof proportional to the change; include real PostgreSQL/browser evidence when the contract crosses those boundaries.
6. Push normally and refetch the new exact head. Do not force-push over concurrent agents.
7. Merge only through normal protected-branch semantics. Otherwise advance to the next eligible PR or product gap.
8. After each merge/closure wave, refresh this baseline, #953, CHANGELOG, and release scope.

Suggested evidence commands from a clean authenticated checkout:

```bash
gh api 'search/issues?q=repo:ContextualWisdomLab/pg-erd-cloud+is:pr+is:open&per_page=1'
gh api 'repos/ContextualWisdomLab/pg-erd-cloud/pulls?state=open&per_page=100'
gh api repos/ContextualWisdomLab/pg-erd-cloud/commits/<exact-head>/check-runs?per_page=100
gh api repos/ContextualWisdomLab/pg-erd-cloud/pulls/<number>/reviews?per_page=100
gh api repos/ContextualWisdomLab/pg-erd-cloud/pulls/<number>/comments?per_page=100
```

PR #943 is the repository's proposed hourly entry point into the central OpenCode review/fix loop. It cannot approve, bypass, or merge around the ruleset. After central `.github` #1153 merges, refresh the immutable reusable-workflow pin and rerun affected Strix heads.

## Release gate

No release candidate exists until all statements below are true at one protected-main commit:

- the intended code, migrations, docs, and release manifest are present;
- every remaining open PR is explicitly outside release scope or the in-scope queue is merged/closed with canonical rationale;
- required backend, frontend, coverage, security, Strix, OpenCode, dependency, filesystem/container, Scorecard, migration, and browser checks are terminal-success;
- zero valid unresolved review/security threads remain and qualifying independent approval exists;
- clean install, upgrade, backup/restore, queue recovery, real PostgreSQL, and buyer browser E2E pass;
- the selected deployment profile, supported dialects/versions, live-apply status, connector status, limits, and non-goals are stated truthfully;
- production coverage/docstring and frontend interaction/accessibility/i18n/design-token contracts meet organization policy;
- capacity/SLO evidence and incident/runbook coverage exist;
- version, CHANGELOG, signed tag, artifact hashes, image digest, SBOM, SLSA provenance, licenses, and rollback instructions identify the release;
- this baseline and `docs/doctoring/product-technical-gap-baseline.md` are refreshed from the final commit.

## Research and standards

See `docs/doctoring/product-technical-gap-baseline.md` for APA 7 references and requirement-to-decision traceability. A citation supports a decision; it does not close an implementation gap or establish certification.
