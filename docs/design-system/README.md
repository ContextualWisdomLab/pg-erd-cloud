# PG ERD Design System

Status: **Design System Draft** (see classification rationale below)
Figma source of truth: `Product Design Kit` — file key `OTN0rBGtnVy0P7yq4Iv9Si`
Related docs: [`docs/ui-ux/README.md`](../ui-ux/README.md)

This document summarizes the Figma-based design system for pg-erd-cloud and
its current mapping to the real codebase. It exists so that engineers do not
need Figma access to understand what tokens/components exist, what is
missing, and which PRs are relevant.

## 1. Figma page structure

The Figma file follows the KRDS-aligned 10-page structure:

| Page | Contents |
|---|---|
| `00. README` | Purpose, scope, must-follow rules, Design System vs UI Kit criteria |
| `01. Foundation` | Color, typography, spacing/layout, radius/shape, icon, elevation |
| `02. Tokens` | Primitive / semantic / component token tiers + naming convention |
| `03. Components` | 6 real `COMPONENT_SET`s with variants + documentation frames (see §3) |
| `04. Basic Patterns` | Table/entity add, column edit, share/export, search/filter, error/empty/loading |
| `05. Service Patterns` | ERD Editor core flow screen + documentation |
| `06. Accessibility` | Grounded in real shipped a11y work (skip-link, focus-visible, `<abbr>` PK/NN, noscript fallback) |
| `07. Dev Handoff` | Figma↔code component mapping + token gap analysis |
| `08. Version & Changelog` | Changelog, deprecation policy, final classification |
| `99. Archive / Deprecated` | Superseded/legacy exploration frames |

## 2. Tokens

### Figma variable collections (source of truth)

- `PG ERD Primitives` — 23 primitive colors (blue/slate/red/green/amber scales)
- `PG ERD Color` — 19 semantic colors, single "Light" mode (dark mode not yet defined — Gap)
- `PG ERD Spacing` — 11-step spacing scale
- `PG ERD Radius` — 4 radius values
- Text styles: `Heading/Large`, `Heading/Medium`, `Body/Default`, `Body/Strong`, `Caption`, `Mono/Small`
- Effect styles: `Shadow/Modal`, `Focus/Ring`

Three semantic variables were added during this pass to close variant gaps:
`color/border/focus`, `color/text/disabled`, `color/border/error`.

### Code-side CSS tokens

`frontend/src/styles.css` previously had **no** `:root` token layer. This PR
adds a minimal, non-duplicative token layer covering only the 3 tokens above,
applied to existing rules without changing any rendered output:

```css
:root {
  --color-border-focus: #034ea2;
  --color-border-error: #b91c1c;
  --color-text-disabled: #9ca3af;
}
```

**This intentionally does not replace or duplicate PR #406
(`codex/css-token-layer`)**, which proposes a much larger, complete
primitive+semantic token layer (~968 lines). That PR is open, `MERGEABLE`,
but blocked on an automated review bot ("OpenCode") that failed due to model
pool exhaustion — not a real content objection (a human/Copilot review found
no issues). Recommendation: re-run/dismiss the stale automated review and
merge #406, then reconcile its token names against the Figma `02. Tokens`
page naming convention.

## 3. Components — Figma ↔ code mapping

| Figma component | Variants added/verified this pass | Real dev component |
|---|---|---|
| PG ERD Button | + Hover/Focus for Primary/Secondary/Ghost | no shared `<Button>` component yet in `frontend/src/` — buttons are ad-hoc `<button>` elements (Gap: extract shared component) |
| PG ERD Input Field | + Error, Read-only states | modal form inputs across `frontend/src/components/modals/*.tsx` |
| PG ERD Table Node | existing, documented | `frontend/src/erd/TableNode.tsx` (PK/NN `<abbr>` a11y from PR #417) |
| PG ERD Status Pill | existing, documented | inline status/badge usages in table/edge UI |
| PG ERD Toolbar Button | existing, documented | toolbar buttons in `frontend/src/App.tsx` |
| PG ERD Share Export Modal | existing, documented | `frontend/src/components/modals/ExportModal.tsx`, `useDialogAccessibility.ts` |

### Known gaps (Figma has it, code doesn't)

- No shared `<Button>` React component — hover/focus/disabled styles are
  duplicated per call site instead of driven by one component with the
  variants now documented in Figma.
- Dark mode: Figma `PG ERD Color` collection only defines a "Light" mode.

### Known gaps (code has it, Figma doesn't yet)

- Full keyboard-navigation flows for the ERD canvas (pan/zoom/select) are not
  modeled as a Figma interactive prototype — only the static "ERD Editor"
  screen exists on `05. Service Patterns`.

## 4. Accessibility

Grounded in real shipped work referenced on the `06. Accessibility` Figma
page: skip-link (`styles.css` `.skip-link`), global `:focus-visible` outline
(now token-driven via `--color-border-focus`), `noscript` fallback, and
accessibility PRs #417, #418, #309, #383.

## 5. Classification

**Design System Draft** — real, reusable component variants and a real
token layer exist in both Figma and (now, minimally) code, but coverage is
incomplete: no shared `<Button>` component in code, no dark mode, and the
larger CSS token layer (PR #406) is not yet merged. Full "Design System"
status should be revisited once PR #406 merges and a shared `<Button>`
component is extracted.

## 6. Follow-ups

1. Merge/re-review PR #406 (`codex/css-token-layer`) — currently blocked by
   a stale automated review, not a real content issue.
2. Extract a shared `<Button>` React component matching the Figma variants.
3. Define a dark-mode variable mode for `PG ERD Color`.
4. Model the ERD canvas keyboard-navigation flow as a Figma prototype.
