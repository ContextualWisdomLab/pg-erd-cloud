# Product & technical gap baseline

**Last updated:** 2026-09-08 UTC (hourly autoresearch fire, issue #1083 /
PR #1100 exact-head `abc7f990` plus Escape-restore follow-up on this branch).

This file is the live ledger for buyer-visible and commercial-readiness gaps.
The epic-level consolidation (#946–#953, stacked increment map, APA references)
lives on PR #1040 (`feat/product-technical-gap-baseline-consolidation-20260901`,
last consolidated 2026-09-02). That PR is open and **blocked** (`frontend`
FAILURE, `noema-review` FAILURE). Do not treat a missing copy on `main` as
“no gaps.” Reconcile this #1083 increment into #1040 when either merges.

Protected `main` at this fire: `8dc746920c12988f082e914879d95e13c9693535`.

## Status legend

| status | meaning |
| --- | --- |
| `in-progress` | exact-head code exists; required checks or review still open |
| `merge-ready-blocked` | increment complete; waiting on a required gate or stack base |
| `spec'd` | issue defines the contract; no merged code |

## #1083 — Single share-and-export toolbar chooser (`bug`, high)

**Job.** A collaborator opens one truthful share-and-export control. The
dialog is a chooser. The toolbar must not advertise SQL, image, UML, or JSON
actions that the dialog cannot perform as distinct shortcuts.

**Decision (GREEN path 1).** Remove the duplicate format-looking toolbar
buttons. Keep a single enabled control when a project can be shared or a
diagram can be exported. Concrete artifacts stay inside `ExportModal`. JSON
remains absent until a versioned JSON export contract exists.

**Exact-head evidence (this fire).**

| item | evidence |
| --- | --- |
| Production delta | `frontend/src/App.tsx` — one `aria-label="공유 및 내보내기"` toolbar button; disabled title `공유할 프로젝트나 내보낼 테이블이 없습니다` |
| Chooser surface | `frontend/src/components/modals/ExportModal.tsx` — SQL DDL, SVG, PlantUML, Mermaid, DBML, Prisma, data-dictionary CSV/Markdown, share link; no JSON control |
| Focus restore | `frontend/src/components/modals/useDialogAccessibility.ts` returns focus to the opener on close, including Escape |
| RED/GREEN tests | `frontend/src/erd/__tests__/App.exportToolbar.test.tsx` — single chooser, no concrete-format toolbar names, no JSON affordance, pointer close, Enter, Space, Escape, disabled empty state |
| Product contract | `docs/ui-ux/product-spec.md` Editor wireframe and collaborator story: one share-and-export chooser |
| Buyer-visible log | `CHANGELOG.md`, `frontend/CHANGELOG.md` Unreleased |

**PR.** #1100 `fix/export-toolbar-single-chooser-1083` (Draft). Frontend and
backend required jobs passed on `abc7f990`; remaining org/security jobs were
queued at fire start. Independent review still required. Real-browser visual
inspection of pointer, Tab, Enter, Space, Escape, focus trap, and empty
disabled state is **not** complete this fire (no running app surface).

**Remaining before promotion.**

1. Exact-head Security Scan, Semgrep, CodeQL, and a qualifying review GREEN.
2. Open the editor in a real browser, capture the toolbar and chooser, and
   compare against `docs/ui-ux/06-erd-editor-main.png` and
   `docs/ui-ux/09-share-export-modal.png`. Do not treat Vitest as that check.
3. Mark ready and merge only after those gates; then close #1083.

**Standards.** W3C. (2024). *ARIA Authoring Practices Guide: Dialog (Modal)
Pattern*. https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/ — Escape
closes the dialog and restores focus to the control that opened it. Accessible
names must match the action the control performs.

## Open high-priority product gaps (not this fire)

| id | status | note |
| --- | --- | --- |
| #1012 | `spec'd` | Isolate diagram-list readiness before fake timers |
| #1010 | `spec'd` | Grammar-specific control-character contracts |
| #764 | `spec'd` | Reject non-text controls in multiline SQL |
| #1014 | blocked | Pin `nanoid` >= 3.3.17 in the frontend lock |
| #1097 | `spec'd` | Access-management control is non-functional |
| #946–#953 | `in-progress` | Epic ledger on PR #1040; stacked OPEN PRs #1056, #1057, #1060, #1063 |

## Stacked increment PRs (do not merge out of order)

- #1057 (`#953` increment 1, base `main`) — BLOCKED (cancelled/failed review jobs)
- #1063 (`#953` increment 2, base #1057) — CLEAN vs its base; waits on #1057
- #1060 (`#947` increment 6) — CLEAN vs `feat/transitive-dependency-assessment-20260902`
- #1056 (`#951` increment 4) — CLEAN vs `feat/perf-baseline-stats-20260901`

## How this document is maintained

Each hourly fire that derives a PRD/TRD/UML/Gap/action from an ADR, exact-head
PR, or issue must update this file in the same slice. Successor fires absorb
#1040’s epic sections rather than rewriting them. Do not record secrets or PII.
