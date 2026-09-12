# Product–Technical Gap Baseline

Status: **Proposed**  
Evidence date: 2026-09-12  
Protected base: `main@8dc746920c12988f082e914879d95e13c9693535`  
Current landing vehicle: PR #1101 (`fix/export-access-status-1097`)

## Goal and bounded context

The `pg-erd-cloud` product owns ERD project access-management presentation and its adapter to the project-member API. Backend project membership remains domain truth; React modal state is a revocable projection and must never replace authorization truth.

Context Map:

```text
Identity subject
  -> Project Access API (membership truth, TLS/CSRF fail-closed)
  -> Access-management adapter (request/mutation generation)
  -> AccessManagementModal (loading/error/permission/save projection)
  -> user decision and retry
```

Share-link bearer access is a separate authorization boundary from project membership. UI copy must not imply that membership revocation invalidates an already issued share link unless the backend contract actually does so.

## Exact-head acceptance matrix

| Area | Exact evidence | Status | Remaining action |
| --- | --- | --- | --- |
| Transport confidentiality | PR #1101 repair `63fd10da…` applies the existing TLS guard before member-list and member-save fetch/CSRF work | GREEN in CI predecessor; preserved in current ancestry | Add real-browser insecure-origin rejection evidence |
| Save close→reopen recovery | RED `3bd5ed8b02044b78326ac5a47fcf8646d3fd49fb`, CI `34692389860`, frontend job `103549838545`: 1 failed / 217 passed; only 2 member reads instead of required 3 | RED reproduced | Closed by source repair below |
| Same-project reconciliation | GREEN `b90a6e4aedf26564a687d77eb4cd0eee9758e7be`, CI `34692601381`, frontend job `103550404399`: 31 test files / 218 tests passed | GREEN | Preserve operation identity and open-project identity as separate invariants |
| Cross-project isolation | `App.accessManagement.test.tsx` rejects late project-A list/save projection after selection moves to project B | GREEN | Add browser-level rapid project-switch evidence |
| Close lifecycle cleanup | Close invalidates list generation and clears loading, saving, error, and member projection | GREEN | Verify focus return and AbortSignal/network cleanup in a real browser |
| Permission/read-only/error states | Modal exposes loading, permission, generic error, saving and disabled states | PARTIAL | Add offline, stale, conflict, retry and read-only Storybook/E2E evidence |
| Responsive/accessibility | Component tests cover dialog semantics; no current-head desktop/mobile/intermediate screenshot or AT transcript | FAIL | Pointer, touch, keyboard, focus return, WCAG 2.2 AA, reduced-motion and screenshot evidence |
| Locale authority | Product copy is not proven against DB-backed versioned ko/en/ja/zh/vi/es/de/fr resources | FAIL | Integrate the translation authority and test CJK/expansion/font fallback |
| Central CodeQL receipt | Current consumer runs dispatch successfully but can remain `VERDICT_STATE=pending` | BLOCKED at canonical `.github` owner | Land the protected handler settlement; rerun only exact failed jobs through the owner |

## Decision record

Problem: a member UPSERT may complete after the access modal is closed and reopened for the same project. The prior single request generation correctly blocked stale UI commits, but it also discarded the successful server mutation and never refreshed the newly opened view.

Constraints:

- the backend remains the canonical writer;
- closing or changing projects must not leak the old project projection;
- a newer save must supersede an older save;
- no force push, source copy, optimistic membership fabrication, or protection bypass;
- failures from a retired modal lifecycle must not appear in a new lifecycle.

Alternatives considered:

1. Keep one generation and ignore every late completion — rejected because a successful server mutation leaves the reopened same-project view stale.
2. Optimistically edit the member array — rejected because presentation state would replace backend truth.
3. Refresh every late completion — rejected because it can cross project/modal boundaries and overwrite newer work.
4. Separate lifecycle request identity, latest mutation identity, and currently open project identity — selected.

Selected behavior: after a successful UPSERT, refresh only when the mutation is still latest and the same project is currently open. The refresh receives a new lifecycle request generation, so it supersedes an older reopened list without overwriting a newer open, close, project selection, or save.

Risks and follow-up:

- network work is logically ignored but not yet aborted; add AbortSignal cleanup and browser coverage;
- server conflicts need a version/ETag contract rather than last-write presentation assumptions;
- exact user and operator scenes require eight-locale evidence and recovery guidance;
- merge remains prohibited until all applicable exact-head Checks and independent review are terminal.

Failure scene: an owner saves `member-1`, closes the modal before the response, and immediately reopens the same project. When the server confirms success, the open modal must re-read backend truth and show the member. If the owner opened another project, closed the modal, or started a newer mutation, the old completion must not alter the visible projection.
