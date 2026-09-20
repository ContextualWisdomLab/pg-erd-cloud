# Test and Release Evidence Strategy

Status date: 2026-08-09
Principle: evidence is attached to the exact commit whose behavior is claimed

## Current executable baseline

| Layer | Exact repository command | Current CI status |
| --- | --- | --- |
| Backend types | `cd backend && PYTHONPATH=. mypy app` | `implemented_on_main` in `.github/workflows/ci.yml` |
| Backend tests | `cd backend && PYTHONPATH=. pytest -q` | `implemented_on_main` |
| Frontend install | `cd frontend && npm ci` | `implemented_on_main` |
| Frontend types | `cd frontend && npm run typecheck` | `implemented_on_main` |
| Frontend unit/component tests | `cd frontend && npm run test` | `implemented_on_main` |
| Frontend production build | `cd frontend && npm run build` | `implemented_on_main` |
| Frontend coverage command | `cd frontend && npm run coverage` | Command exists; no required threshold in CI |
| Browser E2E | `cd frontend && npm run e2e` | Placeholder only; `planned` |
| Documentation contract | `cd backend && PYTHONPATH=. pytest -q tests/test_documentation_contract.py` | `active_pr` with this documentation set |

Passing current CI proves only the commands above. It does not prove 100%
meaningful production coverage, live browser behavior, real PostgreSQL DDL
semantics, deployment TLS, recovery, or visual equivalence.

## Verification layers

| Layer | Required evidence | Applies to |
| --- | --- | --- |
| Documentation contract | Authorities exist, links resolve, ADR index agrees, lifecycle labels and diagrams are present | Every material PR |
| Unit/property | Pure transforms, parser/AST, sanitization, identifiers, diff/order/risk, digest and state transitions | Backend and frontend |
| Component/API | Pydantic/HTTP contracts, tenant roles, public allowlists, focus/keyboard behavior, error states | Current product and PR #824 |
| Database integration | Alembic upgrade from supported prior versions, ORM/schema comparison, constraints, concurrency | Application PostgreSQL |
| Connector integration | Real ephemeral supported database versions, restricted networks, privileges, timeouts | Introspection and FE |
| Browser E2E | Auth, projects, edit/persist, share, responsive layout, keyboard/focus, stale-tab and failure recovery | Commercial user journeys |
| Security | Dependency/SAST/container scan, threat tests, fuzz/property tests, secret/log checks | Exact merge head |
| Operational | Backup/restore, key rotation, queue crash/reclaim, rolling upgrade, rollback, alerts and runbooks | Release candidate |
| Supply chain | Locked dependencies, SBOM, provenance, signed/traceable image and immutable deploy input | Release candidate |

## Current high-risk regression suites

- Project role and IDOR behavior: `backend/tests/test_permissions.py`, API route
  suites, authentication and CSRF suites.
- DSN confidentiality and SSRF: `test_security.py`, `test_dsn_guard.py`,
  connector-specific SSRF tests, and connection API tests.
- Snapshot/queue transitions: snapshot API, worker, snapshot-job and Valkey
  tests. These do **not** currently prove crash reclaim.
- Public share: `backend/tests/test_api_share.py` plus
  `frontend/src/components/SharedDiagramView.test.tsx` on PR #824.
- UI accessibility contracts: dialog tests, keyboard radio-group test, semantic
  token/style tests, and live-Figma comparison evidence. Automated browser and
  assistive-technology evidence remains missing.
- DDL/diff/export: migration, safety, export and property tests. The generated
  output is not proven executable through the deprecated apply endpoint.

## Planned Forward Engineering test matrix

### Semantic model and compiler

- Golden and property tests for normalized model/AST serialization and stable
  digest across ordering noise.
- Quoted, mixed-case, Unicode, reserved-word, multi-schema and overlength
  identifier cases.
- Tables, columns, PK/unique/check/FK constraints, indexes and comments across
  the declared PostgreSQL version matrix.
- Explicit blocking outcomes for views, functions, triggers, types, extensions,
  partitioning, generated/identity columns, RLS, ownership and grants until
  each has a supported capability contract.

### Real PostgreSQL behavior

- Ephemeral clean instances for every supported major version; no mock-only
  acceptance of parser or catalog behavior.
- Migration followed by re-introspection and normalized semantic equality.
- Real lock compatibility, table rewrite, validation, privilege, transaction,
  timeout and `CREATE INDEX CONCURRENTLY` behavior.
- Representative large-table/data-shape fixtures with bounded CI and a
  scheduled extended matrix.

### Failure and recovery

- Target drift immediately before and during execution.
- Duplicate request/idempotency key, two workers, two plans for one target, and
  stale state-version writes.
- Worker termination before statement, during statement, after target commit,
  and before local evidence commit.
- Network partition, primary failover, insufficient privilege, lock timeout,
  statement timeout, cancellation, approval expiry, and partial
  non-transactional completion.
- Backup/restore and operator recovery drill that never reports rollback when a
  segment committed.

## Coverage and documentation quality

QUAL-010 is `planned`. Current CI runs tests without coverage thresholds, and
the backend coverage include list is a subset of production modules. The
quality gate will count owned production branches, exclude only generated or
unreachable defensive code with written justification, mutation-test critical
authorization/planning logic, and require useful public API docstrings.
Mocking the target boundary is useful for unit speed but cannot count as the
critical-path execution proof.

## UI and Figma evidence

PR #824 requires screenshots at the exact live nodes in
[`ui-ux/figma-contract.md`](ui-ux/figma-contract.md), desktop and narrow
viewports, light/dark themes, long/error/empty/success states, and keyboard
focus behavior. Visual similarity does not waive WCAG 2.2 contrast, accessible
name, focus trap/return, scroll, or responsive requirements. The current
browser visual gate is still incomplete and must remain labelled `active_pr`,
not completed.

## Release gate

Before ready-for-review or merge:

1. Rebase/merge evidence is against the exact protected base and head.
2. Every required check is success; queued, skipped, neutral, stale, or
   provider-failed review is not approval.
3. Valid Medium-or-higher dependency/security findings are fixed or narrowly
   documented as genuine false positives without weakening the gate.
4. Independent review resolves every thread; draft-skipped bots are rerun.
5. The traceability and coverage matrices show no implemented requirement with
   missing executable evidence.
6. Upgrade/rollback/recovery and visual/browser evidence required by the change
   are attached before merge.
