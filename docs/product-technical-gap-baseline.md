# Product technical gap baseline

Status: Proposed
Predecessor pull request: #1241
Predecessor exact head reviewed: `4c41d7038008599946b4954bcbe3e2b726572f83`
Successor branch: `codex/design-assurance-pg-erd-cloud-1241-20260930`
Typecheck RED evidence head: `c1f78d1b63f60ce76c3acb1af2f0032395bf5f60`
Test-boundary repair head: `32d73287d549cfb99e6b50d0dfaaa4d031e0f929`

## Goal and ownership

This successor preserves the valid keyboard-accessibility delta from #1241 after a concurrent commit removed the production focus style, regression test, and evidence baseline. pg-erd-cloud remains the canonical writer for its ERD presentation and interaction state; its DTO never replaces database/domain truth.

## Context and acceptance matrix

| Capability | Current evidence | Status | Required action |
| --- | --- | --- | --- |
| Keyboard focus | Focused index name removes clipping, wraps, and shows brand outline | GREEN (source contract) | Keep exact-head unit suite green |
| Exact-value alternative | Index names and access method remain structured DOM text/title | GREEN (source contract) | Verify screen-reader output |
| Pointer/touch, selection, zoom, pan, fit, resize | Current-head browser evidence absent | FAIL | Exercise every applicable ERD interaction |
| Persistence/reload and race cleanup | Not evidenced at current head | FAIL | Verify reload, rollback, stale/conflict, retry, and listener cleanup |
| Responsive layouts | No current-head desktop/mobile/intermediate screenshots | FAIL | Capture three viewport classes |
| WCAG 2.2 AA and reduced motion | Focus rule exists; browser/AT audit absent | FAIL | Run axe, keyboard, touch-target, contrast, and reduced-motion checks |
| UI states | loading/empty/error/offline/permission/read-only/stale/conflict/retry/busy incomplete | FAIL | Add stories/E2E for applicable states |
| Locales | ko/en/ja/zh/vi/es/de/fr evidence absent | FAIL | Add versioned translations and locale E2E |
| Large data, import/export, recovery | Not changed by the focused style, but current evidence absent | FAIL | Run realistic large-schema and recovery scenarios |

## Merge gate

Keep this PR Draft until exact-head Checks, browser interaction, responsive screenshots, accessibility, locale, large-data, import/export, recovery, and required review evidence are green. The predecessor remains open; no valid delta is discarded.
