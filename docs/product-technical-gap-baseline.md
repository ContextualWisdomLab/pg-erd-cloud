# Product–Technical Gap Baseline

Status: Proposed  
Evidence date: 2026-09-19  
Scope: `pg-erd-cloud#1179`, `ExportModal`, protected base `main@8dc746920c12988f082e914879d95e13c9693535`

## Goal / PRD

A user who opens **공유 및 내보내기** must encounter only controls that perform a real product action. Guidance about an unavailable responsibility remains visible and available to assistive technology without adding a dead keyboard stop. A future access-management CTA is allowed only when a product-owned route or callback is wired to an authorized API.

User scene: a keyboard or screen-reader user creates a share link, reads where access policy is managed, exports an artifact, and closes the dialog without landing on a control that cannot act.

Failure scene: a control is exposed as a button but only cancels its own click; users reasonably expect navigation or mutation, yet no route, handler, or API exists.

## Technical Requirements / TRD

- The current access guidance is non-interactive and remains in DOM reading order.
- It has an explicit accessible semantic and name: `role="note"`, `aria-label="접근 관리 안내"`.
- No button named `접근 관리` exists until a real callback and authorized owner API are present.
- Existing share-link and export callbacks remain unchanged.
- Dialog focus trapping, Escape close, and focus return remain owned by `useDialogAccessibility`.
- Presentation text does not create project-permission domain truth; project membership and authorization remain backend-owned.
- A future interactive implementation must add callback/API contract tests, permission/error/loading/busy/retry states, and lifecycle cleanup before the CTA is introduced.

## UML interaction

```text
User -> ExportModal: open 공유 및 내보내기
ExportModal -> User: real share/export controls
ExportModal -> User: non-interactive access-management note
User -> ExportModal: create/copy/export/close
ExportModal -> App callback: requested real action
App callback -> pg-erd-cloud API: authorized request
pg-erd-cloud API -> App callback: domain result/error
```

There is intentionally no `ExportModal -> AccessManagement` interaction in this change because no product route, handler, or API for that action was found at the reviewed head.

## ERD ownership

```text
project_space
  1 ── * project_member
  1 ── * share_link
```

The modal is a presentation adapter. It does not own or mutate `project_member` authorization state. The backend remains the canonical writer for project membership and share-link permission.

## Context Map

```text
[Frontend / Export experience]
  -- callback + HTTP ACL -->
[Backend / Project sharing]
  -- membership authorization -->
[Project identity and membership truth]
```

- Frontend: renders interaction state and invokes supplied callbacks.
- Backend: owns share-link creation and project membership authorization.
- No shared kernel or cross-service database read is introduced.
- Access-management remains a documented future port, not a fabricated UI action.

## Gap / Action / Status

| Gap | Exact evidence | Action | Status |
|---|---|---|---|
| Dead `접근 관리` control | `2d83eec…` used `aria-disabled` plus a click handler that only prevented propagation | Test-first removal; render a named note instead | Repaired in `ea3852f…` → `f2edf4f…` |
| Stale dead-control style | `.exportModal__disabledHintButton` only changed opacity | Remove unused selector | Repaired in `2b22edf…` |
| Product and frontend release notes omitted the semantic boundary | Root and frontend changelogs lacked this repair | Record exact behavior and rationale | Repaired in `0e5f5bc…` and `a276981…` |
| No real access-management owner port | No route, handler, callback, or frontend API was found | Keep guidance non-interactive; design/version the port before adding CTA | Proposed / blocked |
| No real-browser evidence | `frontend/package.json` e2e script reports no framework configured | Add Chromium/Firefox/WebKit pointer, touch, keyboard, AT and lifecycle evidence | Open |
| No locale authority/evidence | Current modal copy is hardcoded Korean | Introduce released screen-key resource contract and validate ko/en/ja/zh/vi/es/de/fr | Open |
| No responsive screenshots | No current-head 320 / 768 / desktop artifacts | Capture exact-revision screenshots and overflow/focus audit | Open |
| No measured large-data responsiveness | No current-head render/interaction median or p95 | Measure realistic large diagrams without sample reduction | Open |

## Exact-head acceptance matrix

| Dimension | Acceptance | Current status |
|---|---|---|
| Determinism | Same props produce the same controls, note, and callback mapping | Candidate PASS; hosted CI pending |
| Semantics | No dead button; named note is present; domain truth stays backend-owned | Source-level PASS after `f2edf4f…` |
| Keyboard / focus | Real controls only in Tab order; focus trap/Escape/return preserved | Unit candidate PASS; real browser missing |
| Pointer / touch | Every exposed control invokes its documented action exactly once | Not evidenced |
| WCAG 2.2 AA / AT | Name, role, value, reading order, focus visible, no obscured focus | Not evidenced in real AT/browser |
| Responsive | 320 px, 768 px, desktop; no clipping or hidden next action | Not evidenced |
| Locale | ko/en/ja/zh/vi/es/de/fr wrapping, CJK and expansion | Not evidenced |
| Loading/error/offline/permission/read-only/stale/conflict/retry/busy | Applicable share/export states are operable and recoverable | Partial unit coverage only |
| Large-data performance | Realistic diagram render/interaction median and p95 recorded | Not evidenced |
| Import/export | Exact values preserved; downloads/copy invoke real callbacks | Existing unit coverage; browser download absent |
| Recovery | Close/Escape/focus return; no stale lifecycle effect after unmount | Hook unit coverage exists; browser evidence absent |

An applicable FAIL or missing exact-revision artifact keeps the PR Draft and not merge-ready.
