# Product and technical gap baseline

- **Snapshot date:** 2026-08-20 (UTC GitHub API evidence; refreshed after normal branch synchronization and PR #824 conflict repair)
- **Repository:** `ContextualWisdomLab/pg-erd-cloud`
- **Base evidence:** `origin/main` = `8dc746920c12988f082e914879d95e13c9693535`
- **Purpose:** turn the current product, architecture, research, and live PR state into an executable release backlog. This is a baseline, not a claim that the product is release-ready.

## Product boundary

pg-erd-cloud is a standalone PostgreSQL-focused ERD collaboration product. It reverse-engineers a target database into immutable schema snapshots, renders and edits an ERD, exports DDL/DBML/Mermaid/data dictionaries/reversing specifications, computes schema diffs and migration-risk evidence, and exposes project-scoped sharing. It must remain independently runnable and consumable as a module by the CWL ecosystem.

The current documented ecosystem boundaries are:

- `naruon`: knowledge-graph and PIM hub;
- `clearfolio`: reference-document conversion/viewer connector;
- `contextual-orchestrator`: OpenAI-compatible model routing/orchestration boundary;
- `.github`: central review, security, scheduler, Strix, Noema, and merge-governance control plane.

The product must not silently become a general-purpose graph database, document viewer, or LLM gateway. Those capabilities belong behind connectors with explicit ownership, authentication, tenancy, and failure contracts.

## Current evidence map

| Area | Current evidence | What it proves | What it does not prove |
|---|---|---|---|
| Backend | `backend/app/api/`, `backend/app/pg_introspect/`, `backend/app/ddl/`, `backend/app/diff/`, `backend/app/spec/` | A broad standalone API and schema-analysis surface exists | Production SLOs, real multi-tenant load, and upgrade-safe migrations |
| Persistence | `backend/app/models.py`, Alembic revisions `0001`–`0007` | Core metadata is relational and most objects use multi-word snake_case names | A complete automated 3NF audit, hot-partition plan, or zero migration drift |
| Background work | `backend/app/jobs/worker.py`, `job_queue`, `FOR UPDATE SKIP LOCKED`, `docs/observability.md` | Queue work is separated from request handling and has basic metrics | High-volume fairness, partition rollover, back-pressure, and regional recovery |
| Frontend | React/Vite ERD editor in `frontend/src/` with Vitest tests; PR #944 adds a Storybook/token inventory | The core canvas, navigation, exports, accessibility, polling, and proposed visual-token contracts are testable | Storybook and browser acceptance on protected main; the PR is not merged yet |
| Real database proof | `frontend/e2e/` and `scripts/run-e2e-with-report.sh` exist only in the current dirty local worktree at capture time | A local PostgreSQL/Playwright proof path has been prepared | That the proof is merged, reproducible in CI, or safe for production targets |
| Ecosystem | `docs/clearfolio-integration.md`, `docs/llm-orchestrator-integration.md` | Connector intent and opt-in boundaries are documented | End-to-end deployed connector contracts and tenant-isolated persistence |
| Design | `docs/ui-ux/` screenshots and product spec; PR #824 contains live-Figma architecture work; PR #944 adds Storybook inventory | Existing visual intent and a Figma-alignment path exist | An approved live Figma handoff or a merged Storybook component contract |
| Governance | root `AGENTS.md`, central ruleset `18156473`, required central workflows, and hourly scheduler PR #943 | Review/security/merge policy and a recurring repair loop are explicit | That every open PR is currently mergeable |

## Buyer-visible gaps, ordered by leverage

| Priority | Gap | Buyer impact | Closure evidence |
|---|---|---|---|
| P0 | The open-PR queue is not release-shaped. The live queue contains 61 PRs and exact-head checks are still in flight across the queue. | Buyers cannot predict what version is safe to deploy or whether a security fix is actually included. | Each PR has a current-head review/check record, resolved threads, normal merge, and release notes; no stale-head claims. |
| P0 | Central Strix bounded scans can produce false evidence: PR #745 reported a credential in scanner-generated `.state/agents.db`; PR #724 reported a missing unchanged PostgreSQL DSN guard in bounded context. The canonical repair is central `.github` PR #1153; duplicate #1164 is closed. | Security gates can block good code or misdirect remediation, delaying releases and weakening trust in the control plane. | Merge #1153 through protected normal review, then collect fresh exact-head Strix runs for affected target PRs. |
| P0 | Alembic and ORM metadata can drift when dependency PRs meet schema changes; PR #838 currently fails its repair check on index/type drift. | Database upgrades can fail at deploy time or silently diverge from the ERD product's own metadata model. | A migration-drift contract on a real PostgreSQL database, upgrade/downgrade proof, and a clean current-head check on #838/#936 dependency order. |
| P0 | Runtime secrets/config still load directly from environment through `backend/app/settings.py`, contrary to the organization KV/credential-registry rule. | Secret rotation, auditability, and least-privilege deployment are weaker than a commercial product requires; PII masking is not a substitute for controlled access. | Bootstrap-only environment transport, encrypted KV reads at runtime, rotation/revocation tests, and no raw runtime `os.getenv()` path. |
| P1 | Schema quality guidance is advisory rather than a complete enforceable contract. Naming lint and wide-table checks exist, but there is no complete 3NF/dependency audit or hot-partition decision record. | Architects receive warnings but not a defensible “safe to operate at scale” assessment. | Versioned 3NF/functional-dependency report, explicit justified exceptions for snapshot JSON, partition/key strategy for queue and event-heavy data, and real seeded-DB tests. |
| P1 | Snapshot history has timestamps and diffing but no first-class temporal lineage, retention, promotion, or rollback workflow. | Teams cannot reliably answer “what changed, when, by whom, and can I restore the known-good model?” | Immutable snapshot lineage API, actor/audit record, retention policy, promotion/rollback UX, and time-ordered integration tests. |
| P1 | Clearfolio and contextual-orchestrator connectors are documented but not complete buyer workflows. Clearfolio explicitly lists project-scoped persistence and frontend attachment as follow-up; LLM integration is opt-in and basic. | A buyer must manually move between tools and cannot rely on durable document/model provenance. | Tenant-scoped connector persistence, signed request/response contract tests, failure/retry UX, model discovery/capability routing, and independent standalone operation. |
| P1 | There is no merged Storybook inventory/design-token contract for repeated web objects. | Visual consistency, accessibility regression detection, and handoff to product teams remain expensive. | Storybook stories for shared controls/modals/ERD states, token source, CSS/token tests, keyboard/interaction tests, and Figma ID in an ADR. |
| P2 | Python owns all introspection and queue hot paths without a measured Rust boundary. | The product has not yet demonstrated predictable CPU use and lowest-context-switch behavior on large schemas. | Benchmark first; introduce a small Rust/WASM or service boundary only for measured CPU/security hotspots, with Python API parity and CPU/GPU decision evidence. Do not rewrite by assertion. |
| P2 | Research provenance is incomplete for normalization, ER modeling, layout, temporal data, and secure software operations. | Product decisions cannot be independently audited by enterprise architects or researchers. | APA 7 citations and redistribution-safe links in `docs/doctoring/`; attach PDFs only when licensing permits. |

## ADR: design authority

The live-Figma work is currently PR #824 (`e34f69c2099d`). The companion ADR is required to record:

- **Figma File ID:** `csnpEEJfmqFWB0vNUoTkWA`
- **Supplemental Figma File ID:** `OTN0rBGtnVy0P7yq4Iv9Si`
- **Authority rule:** Figma is the source for visual intent; Storybook and implementation tests are the executable component contract; screenshots are QA evidence only.
- **Status:** proposed until the PR is reviewed, non-draft, and its live file access/visual sign-off is proven.

## Executable loop

1. The hourly workflow in PR #943 dispatches the central OpenCode review/fix scheduler for up to 100 open PRs; it does not bypass protected review or merge rules. After central #1153 merges, update the immutable workflow pin and revalidate the scheduler PR.
2. Refetch the exact PR head, branch protection/ruleset, review threads, and all check runs.
3. Repair only source-actionable findings at that head; treat provider latency as work to continue around, not as a product conclusion.
4. Re-run focused proof, then the complete required local proof proportional to the change.
5. Push normally, refetch the new exact head, and wait for fresh checks/review.
6. Merge only with normal protected-branch semantics; otherwise advance to the next eligible PR or product gap.
7. After a merge, refresh this baseline's live queue evidence and CHANGELOG/release state.

## Current open PR inventory (live refresh)

The live REST API returned **61 open PRs** at this refresh. Each SHA below is
the exact head used for review/check triage; a merge decision must refetch it
again because remote agents and required workflows can change it.

| PR | Exact current head | Title |
|---:|---|---|
| #944 | `d393bf655171fb31de0a8cc6c9517ba69aa3c9fc` | Storybook design-token inventory |
| #943 | `a968d54daf1ddd663b801628a7817f4c5bf459ba` | hourly PR review repair scheduler |
| #942 | `62ba4cc490ff4b124d3ba1d7e0f027d539492bd7` | product and technical gap baseline |
| #941 | `18a91beac732f2cf41f3971087adf76ad283318c` | API key hashing |
| #940 | `9fb1c3b221a066de4b5ccba6d474a9695683720d` | Snowflake constraint grouping |
| #939 | `3ca5db715db50ee01f061131c02f57e82493f85e` | ERD export handle validation |
| #938 | `dc50a22140c636ba9ca1f58bb8b769d1eb3ff33d` | MySQL introspection grouping |
| #936 | `5e73610f345535ce19f993561b728cfeb54f92e0` | ORM metadata and migration reconciliation |
| #933 | `ec54f20321b9caf5d7a29f84b4c608dd0f6f552d` | automatic column mapping |
| #930 | `aaffad0a8c126ce089e873d323cbc70797aef5e8` | required form-field indicators |
| #926 | `369d82c491d3e029bcaff80487fc5885d87d7c2d` | control-character schema rejection |
| #915 | `34e088c0a93928a9902a13a0e1b4ad3d8e544f03` | table-delete confirmation |
| #914 | `df336c0dec6177b5c67299591c789dcbdb555a33` | CodeQL analyze update |
| #913 | `d70622107200a998b36a761666f74ea2c70b5efd` | CodeQL init update |
| #912 | `802441e60f21769711d6bf93b8b797bd697fc7b3` | CodeQL autobuild update |
| #910 | `5c1412bf3ec1236b3de879345fca2bc724af2212` | jest-dom update |
| #909 | `d3faffdd5407892148939eb1e278fd9150de573c` | Snowflake connector update |
| #907 | `c6131676e4dfa79230e8ea4b61e8e8485d710552` | setuptools update |
| #906 | `3c6db17b4943508c384761716a0f7d19f9aed5b3` | SQLAlchemy update |
| #905 | `0070a2967b9dacf5f9033b62a530b65b638ff695` | Starlette update |
| #904 | `4a80d4ec41f818a74268cad86fa493fc0e292e0b` | Python image update |
| #903 | `3c7a574799bf7e6a3b5a6ee8a1066eaba15c87e1` | Prisma collision-free identifiers |
| #902 | `57ff32131c7a28d9d5ed146325a327c687b1ea49` | NVIDIA NIM OpenCode routing |
| #901 | `eeef7b7170a21e8f191482b6913f75356341c0ec` | business-group color radiogroup |
| #900 | `ed12e8d6e2ae75e4591827fe4315d4d7a53b9374` | adaptive LLM orchestration |
| #895 | `8436cb4b8ce7f5bdda897f8c13c2aa51ea9511e8` | JWT critical-header rejection |
| #894 | `f67f8888d917b27107f68d17f9b13f1ab429d7bf` | Prisma relation index |
| #890 | `a04935ded27fb4817a76682c3b6e01c63e03e32c` | authenticated project-list contract |
| #889 | `f7cd3c62c5ea69df3607481519264251d6d81510` | CodeQL backfill inputs |
| #888 | `6f47fe0f29135699101ac4179cb668acd8b423ca` | Valkey sentinel host contract |
| #887 | `d221ab7951047ec84c11bc5707faaf4571269909` | log-breaking identifier rejection |
| #886 | `c7a45292dbb6ad26f9d0cfef83bd9d5d9ecb1635` | current-user HTTP contract |
| #884 | `4499ab534ce3b3d7d09aa45a24565c165f24dde1` | ERD handle-array removal |
| #882 | `b924d0917e3ab4d2de674be4277d1634f03860db` | modal action ARIA labels |
| #881 | `5a8ce593bc8b94c89c4cab0b9af36784a0dd472a` | immutable search memoization |
| #874 | `a0c816003b13f4d6cb6f016ca739a9012e424dac` | DBML index evidence |
| #868 | `d9f1b9478492595937b7382f6876e0a4c134dda9` | server-local DSN rejection |
| #858 | `a34b35e59bf76d8b311be041e040f0f1148b63e3` | unavailable toolbar actions |
| #857 | `63424a49e4345f5f8305d85188d9a46349d407fe` | bounded Unity Catalog introspection |
| #856 | `322d543386c2658e563ae383780847f51f767fb9` | relationship-aware ERD layout |
| #855 | `b94eb617708782ccda5e5a3c199c749fbbf32a80` | OIDC organization binding |
| #850 | `682f107782bd7a9d5b5605de7d78402dc71cdd21` | ERD column-name resolution |
| #838 | `d5b52f80ca24480c0000d20d75b568ff9a62b9a4` | Alembic dependency update |
| #835 | `423564054a82e4158219cf56a9348652265e12da` | native form submission paths |
| #834 | `07a4e376ba0ed1ae2fead9892ba66f4b54b14c8d` | forward-engineering plan authority |
| #832 | `35c12f43a045040c7b10f527528039cd014a678d` | non-text multiline SQL rejection |
| #827 | `e99129920ba981ecd3a529451756489aaa3f7f5a` | concurrent pooler detection |
| #824 | `e34f69c2099d0e37cd04efe5b974515d0678476d` | live Figma and sharing architecture |
| #782 | `5057b01e0b1aaae3fab7852360dd4b99dd49b732` | PostgreSQL SYSTEM_USER naming |
| #774 | `20afa6790cf8191173639d98c23b549de64e8a23` | PostgreSQL identifier inference |
| #772 | `b6bf1d460c43d801b725f7e3600512c90588a02c` | dead relationship lookup removal |
| #768 | `03d637684658ed4f501ef7a0c9d7a101b5123e40` | missing-column rendering test |
| #745 | `7c8afef1fde51e6c5086aa342f008f7aadbf4796` | DSN secret redaction |
| #744 | `409343ce286f49b5a700200b6cca1a5d7e159f0c` | supported CORS methods |
| #738 | `43d594c9d955b273875c3234c02333439a819878` | diagram-data deflake |
| #737 | `8e58fc0867ab909d427724064daefa1397bac48e` | ecosystem names and review policy |
| #725 | `203dce1b0ad4e79e709ce0c796c457d065db4fae` | FastAPI and Redis lock synchronization |
| #724 | `dbc315867013fbf0481853039ec53d75e6101743` | trusted local PostgreSQL snapshot CLI |
| #723 | `2a65c8263d325c5e4fcef51d95ee57e411cf4e49` | saved-layout update contract |
| #704 | `5f10da2a4bf4b4db93762281a5886650b74887a3` | unavailable table-save accessibility |
| #698 | `00eb7938217eeae51ed12c7188c85b36e5414174` | unavailable export accessibility |

The previous inventory below is retained as historical evidence from the first
baseline capture and must not be used for a merge decision.

## Historical open PR inventory

The following inventory was queried from the live REST API and records the exact head used for triage on 2026-08-20. It is intentionally a snapshot; the verification command below must be rerun before every merge decision.

| PR | Exact head | State | Title |
|---:|---|---|---|
| #944 | `d4989bd13c04` | ready | feat(frontend): add Storybook design-token inventory |
| #943 | `c7289801c7eb` | ready | ci: schedule hourly PR review repair |
| #942 | `7fb0061937e28` | ready | docs: establish product and technical gap baseline |
| #941 | `18a91beac732` | ready | fix(auth): offload API key hashing |
| #940 | `9fb1c3b221a0` | ready | refactor(snowflake): group constraint context |
| #939 | `3ca5db715db5` | ready | fix(frontend): validate ERD export handles |
| #938 | `dc50a22140c6` | ready | refactor(mysql): group introspection rows |
| #936 | `007fb6696c13` | ready | fix(db): reconcile ORM metadata with migrations |
| #933 | `ec54f20321b9` | ready | feat: add automatic column mapping and default fk label on edge creation |
| #930 | `aaffad0a8c12` | ready | 🎨 Palette: Add visual indicators for required form fields in modals |
| #926 | `369d82c491d3` | ready | 🛡️ Sentinel: [MEDIUM] Fix control character injection in Pydantic schemas |
| #915 | `34e088c0a939` | ready | 🎨 Palette: [테이블 삭제 시 확인창 추가] |
| #914 | `b2a265fa0f12` | ready | chore(deps): bump github/codeql-action/analyze from 4.36.2 to 4.37.7 |
| #913 | `d70622107200` | ready | chore(deps): bump github/codeql-action/init from 4.36.2 to 4.37.7 |
| #912 | `802441e60f21` | ready | chore(deps): bump github/codeql-action/autobuild from 4.36.2 to 4.37.7 |
| #910 | `5c1412bf3ec1` | ready | chore(deps-dev): bump @testing-library/jest-dom from 6.9.1 to 7.0.1 in /frontend |
| #909 | `d3faffdd5407` | ready | chore(deps-dev): update snowflake-connector-python requirement from <5,>=4 to >=4.7.2,<5 in /backend |
| #907 | `c6131676e4df` | ready | chore(deps-dev): update setuptools requirement from >=82.0.1 to >=84.0.0 in /backend |
| #906 | `3c6db17b4943` | ready | chore(deps): update sqlalchemy requirement from <2.1,>=2.0.51 to >=2.0.52,<2.1 in /backend |
| #905 | `0070a2967b9d` | ready | chore(deps): update starlette requirement from >=1.1.0 to >=1.6.0 in /backend |
| #904 | `4a80d4ec41f8` | ready | chore(deps): bump python from 3.14.6-slim to 3.14.7-slim in /backend |
| #903 | `e83f606e4a89` | ready | feat(prisma): allocate collision-free identifiers with @map |
| #902 | `57ff32131c7a` | ready | chore(opencode): use NVIDIA NIM only |
| #901 | `eeef7b7170a2` | ready | fix(a11y): restore business-group color radiogroup contract |
| #900 | `ed12e8d6e2ae` | ready | feat(ai): delegate LLM drafts to adaptive orchestration |
| #895 | `8436cb4b8ce7` | ready | security(auth): reject unsupported JWT critical headers |
| #894 | `0fb24c0f11d1` | ready | perf(prisma): index outgoing relation lookup |
| #890 | `a04935ded27f` | ready | test(api): verify the authenticated project-list contract |
| #889 | `f7cd3c62c5ea` | ready | security(ci): harden manual CodeQL backfill inputs |
| #888 | `6f47fe0f2913` | ready | test(valkey): verify sentinel host formatting contracts |
| #887 | `d221ab795104` | ready | fix(security): reject log-breaking identifier characters |
| #886 | `c7a45292dbb6` | ready | test(api): verify the current-user HTTP contract |
| #884 | `4499ab534ce3` | ready | perf(frontend): remove intermediate ERD handle-ID array |
| #882 | `b924d0917e3a` | ready | 🎨 Palette: 모달 내 일반 액션 버튼에 컨텍스트 ARIA label 추가 |
| #881 | `5a8ce593bc8b` | ready | perf(search): memoize immutable ERD searchable text |
| #874 | `a0c816003b13` | ready | fix: preserve DBML index evidence |
| #868 | `d9f1b9478492` | ready | security(postgres): reject server-local file access via DSNs |
| #858 | `a34b35e59bf7` | ready | a11y(frontend): keep unavailable toolbar actions discoverable |
| #857 | `63424a49e434` | ready | feat(databricks): add bounded Unity Catalog introspection |
| #856 | `322d543386c2` | ready | feat(frontend): add relationship-aware ERD layout |
| #855 | `b94eb6177087` | ready | fix(auth): bind OIDC tokens to configured organization |
| #850 | `682f107782bd` | ready | ⚡ Bolt: Optimize ERD column name resolution |
| #838 | `d5b52f80ca24` | ready | chore(deps): update alembic requirement from >=1.18.5 to >=1.19.1 in /backend |
| #836 | `d88f98b9cd9f` | ready | chore(deps): bump node from 26.5.0-alpine to 26.7.0-alpine in /frontend |
| #835 | `423564054a82` | ready | fix(a11y): use native form submission paths |
| #834 | `8ee872eb0e39` | ready | feat: establish forward engineering plan authority |
| #832 | `35c12f43a045` | ready | security(api): reject non-text controls in multiline SQL |
| #827 | `e99129920ba9` | ready | ⚡ Bolt: [concurrent pooler detection] |
| #824 | `db59f97b16cb` | draft | feat: align live Figma, harden sharing, and establish architecture authority |
| #782 | `602edabbb974` | ready | fix(naming): classify PostgreSQL SYSTEM_USER as reserved |
| #774 | `f19848ab187b` | ready | fix(erd): preserve PostgreSQL identifiers in relationship inference |
| #772 | `917064279217` | ready | chore(backend): remove dead relationship-inference lookup |
| #768 | `1dbd7f919720` | ready | test(data-dictionary): cover missing-column rendering |
| #745 | `5887448da640` | ready | 🛡️ Sentinel: [CRITICAL] Fix incomplete DSN secret redaction and over-redaction |
| #744 | `e56490223e35` | ready | fix(cors): allow every supported API method |
| #738 | `52c66dde059f` | ready | test(frontend): await diagram data before search assertion (deflake main) |
| #737 | `cc08088001d6` | ready | docs: align ecosystem names and solo-maintainer review policy |
| #725 | `6de38790e3cc` | ready | chore(deps): synchronize FastAPI and Redis backend locks |
| #724 | `dd2d27930bcb` | ready | feat: add trusted local PostgreSQL snapshot CLI |
| #723 | `bdce888ce64b` | ready | feat(diagram-views): complete saved-layout update contract |
| #704 | `6608a4995427` | ready | a11y(frontend): expose unavailable table-save state to keyboard users |
| #698 | `0a5b86f23a42` | ready | a11y(frontend): keep unavailable export actions discoverable |

## Verification command

Run from a clean checkout with GitHub authentication:

```bash
gh api 'repos/ContextualWisdomLab/pg-erd-cloud/pulls?state=open&per_page=100'
gh api repos/ContextualWisdomLab/pg-erd-cloud/commits/<exact-head-sha>/check-runs?per_page=100
gh api repos/ContextualWisdomLab/pg-erd-cloud/pulls/<number>/reviews?per_page=100
gh api repos/ContextualWisdomLab/pg-erd-cloud/pulls/<number>/comments?per_page=100
```

At collection time, the exact-head completed-failure scan identified PR #838 (`repair`), PR #745 (`strix`), and PR #724 (`strix`). PR #838 is the ORM/migration drift that PR #936 addresses; #724/#745 require the canonical central Strix repair before their scans are re-evaluated. PR #914's frontend failure was reproduced from its job log, repaired with commit `b2a265fa`, and its checks were requeued. These are mutable external facts; a later run must not reuse them without refetching.

## Release gate

A release candidate is not established until:

- protected main contains the intended code and migrations;
- the exact-head open-PR inventory is empty or every remaining PR is explicitly out of release scope;
- backend, frontend, security, Strix, Noema, coverage, and migration checks are green;
- real seeded PostgreSQL + browser acceptance passes;
- connector failure/authorization paths are tested;
- CHANGELOG and version/tag evidence identify the release;
- the current ADR and doctoring references are present.

## References

See `docs/doctoring/product-technical-gap-baseline.md` for APA 7 references and research traceability.
