# KRW 2B Commercialization Plan

This plan is the concrete operating plan for making `pg-erd-cloud` credible as a
KRW 2B enterprise SaaS or on-premises product. KRW 2B is treated here as a buyer
confidence threshold for an enterprise-grade product package, not as a revenue
guarantee.

The active GitHub PR is `#415` on `product/commercial-readiness`. Review-bot
latency and queued automation are not blockers. Only actual CI failures,
security defects, missing sellable features, and unverifiable deployment or
operating paths block release.

FigJam operating model:
https://www.figma.com/board/XJXqiPUAYyrV85N5XzQpsB?utm_source=codex&utm_content=edit_in_figjam&oai_id=&request_id=abef7f56-0ca9-4a97-9173-0e6ecb254b71

## Tool Roles

### Superpowers

- Maintain this execution plan as the source of truth for sequencing.
- Convert every gap into a testable task with a named file, acceptance criteria,
  and verification command.
- Keep execution autonomous after the plan is written; do not wait for review
  bot comments or approval-only delays.

### Product Design

- Audit the core product flows from the buyer's point of view:
  authentication, first-run onboarding, project creation, connection setup,
  snapshot creation, ERD editor use, share/export, billing handoff, and support.
- Classify UX findings as:
  - `P0`: blocks trust, activation, security comprehension, or purchase.
  - `P1`: reduces conversion, retention, or supportability.
  - `P2`: polish or scale improvement.
- Keep every finding tied to a running-app screenshot, source component, Figma
  node, and implementation task.

### Figma

- Do not use Figma Code Connect.
- Use Figma and FigJam for editable product screens, flow diagrams, QA boards,
  buyer-trust walkthroughs, release-gate boards, and visual regression evidence.
- Extend the existing product design file and FigJam boards before creating
  separate design artifacts.
- Use Figma screenshots only as evidence. The implementation source remains the
  repository.

### Data Analytics

- Build the KRW 2B buyer-confidence model with transparent assumptions:
  target customer profile, problem severity, price packaging, deployment model,
  sales motion, support cost, activation funnel, retention risk, and expansion
  path.
- Define the product KPIs and guardrails required before a KRW 2B valuation or
  enterprise contract discussion:
  activation rate, connection success rate, snapshot success rate, ERD render
  latency, share/export success rate, license validation success, billing
  reconciliation success, restore drill success, incident response times, and
  support load.
- Mark missing market data explicitly instead of hiding it in estimates.

### Ponytail

- Keep the implementation boring and direct.
- Do not add a submodule now. A submodule would add operational friction without
  a proven independent release boundary.
- Do not split a separate library now unless one of these triggers is met:
  - A module is consumed by backend, frontend, CLI, and external customers.
  - A customer needs independent versioning or vendoring.
  - The module has a stable public API with tests and release notes.
  - Keeping it inside the app makes security review or on-prem packaging harder.
- Current candidate for future extraction:
  - `commercial-license-kit`: license token verification, revocation-list
    parsing, offline issuance helpers, and contract fixtures.
  - Keep it in-repo first under existing backend code until a second consumer
    exists. If extraction becomes justified, prefer a normal package in a
    monorepo workspace over a git submodule.

## Commercial Release Gates

### P0: No-Go Until Complete

- Security:
  production startup refuses weak secrets, missing OIDC issuer/audience,
  unsafe CORS, missing target database allowlist, and unbounded public share
  behavior.
- Authentication:
  signed-in, signed-out, forbidden, and deactivated-account states are distinct
  in API responses and UI copy.
- Authorization:
  project ownership, membership, share-link permissions, and admin-only
  operations are covered by tests.
- Data protection:
  DSNs and tokens are redacted from logs, exports, errors, and telemetry.
- Billing and license:
  signed license validation, revocation, usage limits, account deactivation,
  reactivation link exposure, and plan-change handoff are implemented and
  tested.
- Deployment:
  Docker/prod compose path, environment documentation, database migration path,
  backup/restore, and rollback runbook are reproducible.
- Quality:
  backend tests/mypy, frontend typecheck/unit/build, E2E, accessibility, visual
  regression, approval-manifest validation, and security scans have no real
  failures on the current head.

### P1: Paid Pilot Required

- Billing provider reconciliation:
  provider-neutral webhook/event ingestion records payment or contract events,
  deduplicates events, maps them to account state, and exposes support evidence.
- Admin and support console:
  authorized operators can inspect account state, license status, billing usage,
  share links, and deactivation/reactivation context without direct database
  access.
- Observability:
  alerts have owner, severity, threshold, customer impact, and first response
  guidance. Metrics cover auth failures, share failures, billing/license
  failures, snapshot jobs, queue latency, and restore drills.
- On-premises package:
  offline license issuance, revocation list update, air-gapped deployment notes,
  backup/restore drill, and upgrade rollback are documented and smoke-tested.
- UX buyer trust:
  first-run, billing, share/export, errors, and empty states explain what
  happened and what the user can do next.

### P2: General Availability

- Multi-browser visual baselines beyond Chromium for buyer-critical workflows.
- Customer-facing release notes and support playbooks for each commercial
  release.
- Formal market sizing and pricing sensitivity evidence.
- Legal approval manifest filled with real approver/date/version records.
- Optional external package split if a second consumer proves the boundary.

## Execution Work Packages

### 1. Live Audit Refresh

Files:

- `docs/commercial-readiness.md`
- `docs/superpowers/plans/2026-07-02-krw-2b-commercialization.md`

Tasks:

- Recheck `main`, PR `#415`, unresolved review threads, required checks, and
  branch mergeability.
- Treat queued review and bot-only lag as non-blocking.
- Record only real failed checks or unmerged high-risk gaps as blockers.

Verification:

```bash
gh pr view 415 --repo ContextualWisdomLab/pg-erd-cloud --json headRefOid,mergeable,mergeStateStatus,reviewDecision,statusCheckRollup
gh pr checks 415 --repo ContextualWisdomLab/pg-erd-cloud --required
```

Acceptance:

- Current head SHA is recorded in the final work summary.
- Any failed required check has a follow-up implementation task.

### 2. Data Analytics Buyer Model

Files:

- `docs/business/krw-2b-market-kpi-model.md`

Tasks:

- Define ICP segments:
  platform teams, data engineering teams, consulting/SI teams, regulated
  database operations teams, and on-premises enterprise buyers.
- Create a transparent KRW 2B model:
  enterprise license, on-prem support, annual recurring subscription, services,
  and expansion scenarios.
- Define KPI thresholds:
  activation, connection success, snapshot success, ERD render latency,
  share/export success, license validation, billing reconciliation, restore
  drill, incident response, and support effort.
- Mark every assumption as `measured`, `estimated`, or `missing`.

Verification:

```bash
git diff --check docs/business/krw-2b-market-kpi-model.md
```

Acceptance:

- No market claim is presented as proven without evidence.
- The model states what evidence must be collected before sales collateral can
  make numeric claims.

### 3. Product Design Audit Expansion

Files:

- `docs/ui-ux/product-design-audit.md`
- `docs/ui-ux/design-qa-checklist.md`

Tasks:

- Add buyer-trust checks for:
  first-run onboarding, empty workspace, connection errors, billing limits,
  plan-change handoff, account deactivation, share/export success, and support
  escalation.
- Convert every `P0` design issue into a frontend task with test coverage.

Verification:

```bash
git diff --check docs/ui-ux/product-design-audit.md docs/ui-ux/design-qa-checklist.md
```

Acceptance:

- Every buyer-critical state has either existing visual evidence or a task to
  add visual evidence.

### 4. Figma And FigJam Commercial Board

Files:

- `docs/ui-ux/product-design-figma-execution-plan.md`
- Existing Figma design file
- Existing and new FigJam boards

Tasks:

- Link the KRW 2B commercial readiness FigJam board.
- Add a buyer walkthrough lane:
  discovery, trial, security review, procurement, deployment, renewal.
- Add a release-gate lane:
  P0 no-go, P1 paid pilot, P2 GA, evidence, owner, and verification command.
- Keep Code Connect unused.

Verification:

```bash
git diff --check docs/ui-ux/product-design-figma-execution-plan.md
```

Acceptance:

- Figma/FigJam artifacts are linked from repository docs.
- The design artifacts explain release gates without becoming the source of
  implementation truth.

### 5. Billing Provider Reconciliation

Files:

- `backend/app/api/billing.py`
- `backend/app/schemas.py`
- `backend/tests/test_billing_usage.py`
- `docs/legal/license-billing.md`

Tasks:

- Add provider-neutral billing event schema:
  provider, provider event id, event type, subject, target plan, occurred time,
  status, and metadata redaction.
- Add idempotent event ingestion endpoint guarded by a shared secret or signed
  provider token.
- Record event outcomes for support diagnostics.
- Keep the existing portal/support handoff path.

Verification:

```bash
cd backend
PYTHONPATH=. uv run pytest -q tests/test_billing_usage.py
PYTHONPATH=. uv run mypy app
```

Acceptance:

- Duplicate events do not double-apply state changes.
- Invalid signatures or missing secrets fail closed.
- No raw customer secrets appear in response bodies or logs.

### 6. Admin Support Surface

Files:

- `backend/app/api/*`
- `backend/tests/*`
- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `frontend/src/styles.css`
- `frontend/src/App.accessibility.test.tsx`

Tasks:

- Expose read-only admin/support account diagnostics for account state, usage
  limits, license verification mode, reactivation URL, support URL, and recent
  billing events.
- Add frontend support view only for authorized operators.
- Keep destructive actions out of the first implementation slice unless tests
  and audit logs are in place.

Verification:

```bash
cd backend
PYTHONPATH=. uv run pytest -q
PYTHONPATH=. uv run mypy app
cd ../frontend
npm run test:a11y
npm run typecheck
npm run test -- --run
npm run build
```

Acceptance:

- Non-admin users cannot access support diagnostics.
- Admin view is useful without requiring direct database access.

### 7. On-Premises Packaging Drill

Files:

- `docs/operations/backup-restore.md`
- `docs/operations/migration-rollback.md`
- `docs/legal/license-billing.md`
- `deploy/*`

Tasks:

- Add an on-prem deployment checklist covering offline license issue,
  revocation-list update, secret rotation, backup, restore, upgrade, rollback,
  and support bundle collection.
- Add a smoke command or script for validating the documented package path.

Verification:

```bash
git diff --check docs/operations/backup-restore.md docs/operations/migration-rollback.md docs/legal/license-billing.md
```

Acceptance:

- A buyer can evaluate whether the product can be installed and supported
  without SaaS connectivity.

### 8. CI And PR Loop

Files:

- PR `#415`
- `.github/workflows/*`
- `scripts/ci/*`

Tasks:

- Monitor required checks on the current head.
- Ignore queue latency.
- Fix real failures immediately in the same branch when scoped to the current
  commercialization work.
- Avoid widening workflow permissions unless the failure proves a real
  permission gap.

Verification:

```bash
gh pr checks 415 --repo ContextualWisdomLab/pg-erd-cloud --required
```

Acceptance:

- Required checks on the latest head are successful or only queued/pending.
- Any failed check has a commit that directly addresses the failing log.

## First Autonomous Slice

Execute these next, in order:

1. Commit this KRW 2B plan and link it from commercial readiness docs.
2. Add `docs/business/krw-2b-market-kpi-model.md` with the initial Data
   Analytics KPI and assumption model.
3. Update the Figma/Product Design execution doc with the new FigJam board and
   no-Code-Connect constraint.
4. Re-run lightweight doc validation.
5. Push to PR `#415`.
6. Recheck required PR checks and only intervene on actual failures.
