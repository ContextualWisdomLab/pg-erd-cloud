# Product technical gap baseline

Status: Proposed
Predecessor pull request: #1241
Predecessor exact head reviewed: `4c41d7038008599946b4954bcbe3e2b726572f83`
Typecheck RED evidence head: `c1f78d1b63f60ce76c3acb1af2f0032395bf5f60`
Node-boundary repair head: `32d73287d549cfb99e6b50d0dfaaa4d031e0f929`
First hosted-test RED head: `c54389e8b63f4553694e1d12d952fe3be034af2a`
Second hosted-test RED head: `3cc5fe6f82c3d21d275745067e3b9e25e0e22871`
Native CSS-contract implementation head: `bea4bc808f0705b390edd8d838bf091a776dd9d2`

## Goal and ownership

This successor preserves the valid keyboard-accessibility delta from #1241 after a concurrent commit removed the production focus style, regression test, and evidence baseline. pg-erd-cloud remains the canonical writer for its ERD presentation and interaction state; its DTO never replaces database/domain truth.

## Root-cause evidence

CI run `36726543573`, frontend job `109924762084`, first proved that adding `node:fs` to the TypeScript/Vitest test violated the frontend type boundary. After removal, Vitest still returned no match for `styles.css?raw`.

CI run `36733329790`, frontend job `109948423351`, checked the next exact head, passed typecheck, and again reported 201 passed with one failure at the same selector assertion after `?inline`. The repeated result proves the issue is Vitest's CSS transformation boundary rather than the product rule or a query suffix.

The focused stylesheet contract now runs with Node's standard `node:test` and `node:fs` in a separate JavaScript test process before Vitest. It reads the real production file directly, adds no dependency or ambient type, and leaves component tests under Vitest. A new hosted run is required before claiming GREEN.

## Context and acceptance matrix

| Capability | Current evidence | Status | Required action |
| --- | --- | --- | --- |
| Keyboard focus | Focused index name removes clipping, wraps, and shows brand outline | GREEN (source contract) | Require new exact-head hosted test GREEN |
| Test execution boundary | Native Node CSS test plus existing Vitest component suite; no custom loader or dependency | REPAIRED, NOT REVALIDATED | Confirm both test processes on the new exact head |
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
