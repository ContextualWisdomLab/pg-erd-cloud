# PG ERD Design System

Status: **Design System Draft** (see classification rationale below)
Target Figma file: `Product Design Kit` — file key `OTN0rBGtnVy0P7yq4Iv9Si`
Related docs: [`docs/ui-ux/README.md`](../ui-ux/README.md)

This document summarizes the repo-backed KRDS design-system inventory for
pg-erd-cloud and its current mapping to the real codebase. Direct Figma MCP
tools (`use_figma`, screenshots, metadata, library search) were unavailable in
this environment, so Figma pages/components/variables are treated as target
structure until they can be inspected or mutated directly.

For the **full KRDS traversal** (all 37+ components, 12 basic patterns, 5
service patterns) with per-item status and the machine-checkable Gap Report,
see [`krds-inventory.md`](./krds-inventory.md) — that file is the authoritative,
version-controlled mirror of the Figma inventory pages.

## 1. Target Figma page structure

The target Figma file should follow the KRDS-aligned **21-page** structure
(components split by KRDS category, plus a dedicated Gap Report):

| Page | Contents |
|---|---|
| `00. README` | Purpose, scope, adoption level, DS/UI-Kit criteria, naming/versioning rules |
| `01. Foundation` | Color, typography, shape/radius, layout, icon, elevation, **High Contrast Mode** |
| `02. Tokens` | Primitive / semantic / component token tiers + naming convention |
| `03. Components - Identity` | Masthead, identifier, header, footer (KRDS inventory) |
| `04. Components - Navigation` | Skip link, main/side menu, breadcrumb, pagination (inventory) |
| `05. Components - Layout & Expression` | Modal, Badge, Table Node component-set records (inventory) |
| `06. Components - Action` | **Button** + Toolbar Button component-set records (inventory) |
| `07. Components - Selection` | Radio, checkbox, select, tag, toggle (inventory) |
| `08. Components - Feedback` | Step indicator, spinner (inventory) |
| `09. Components - Help` | Tooltip, contextual help, coach mark, TTS (inventory) |
| `10. Components - Input` | **Input Field** component record + text/date/file inputs (inventory) |
| `11. Components - Setting` | Language switcher, text resize (inventory) |
| `12. Components - Content` | Accessible media, hidden content (inventory) |
| `13. Components - Mobile` | Toast, snackbar, bottom sheet, back button (inventory) |
| `14. Basic Patterns` | KRDS 12 basic patterns inventory + target pattern frames |
| `15. Service Patterns` | KRDS 5 service patterns inventory + ERD core flow prototype |
| `16. Accessibility` | Grounded in shipped a11y work (skip-link, focus-visible, `<abbr>`, noscript) |
| `17. Dev Handoff` | Figma↔code component mapping + token gap analysis |
| `18. Version & Changelog` | Changelog (v0.1–v0.5), deprecation policy, classification |
| `19. Gap Report` | KRDS Area / Reference / Issue / Severity / Action / Owner / Due |
| `99. Archive / Deprecated` | Superseded/legacy exploration frames |

The repo mirror records 6 component-set targets distributed to their KRDS
categories: Button & Toolbar Button → Action (06); Input Field → Input (10);
Table Node, Status Pill (Badge) & Share/Export Modal → Layout & Expression
(05). These still need direct Figma verification.

## 2. Tokens

### Target Figma variable collections (pending direct verification)

- `PG ERD Primitives` — 23 primitive colors (blue/slate/red/green/amber scales)
- `PG ERD Color` — 22 semantic colors, **two modes: `Light` + `High Contrast`** (선명한 화면 모드, KRDS style_09; 12 tokens overridden for high contrast). Dark mode still undefined — Gap.
- `PG ERD Spacing` — 11-step spacing scale
- `PG ERD Radius` — 4 radius values
- Text styles: `Heading/Large`, `Heading/Medium`, `Body/Default`, `Body/Strong`, `Caption`, `Mono/Small`
- Effect styles: `Shadow/Modal`, `Focus/Ring`

The repo mirror records three semantic variables to close variant gaps:
`color/border/focus`, `color/text/disabled`, `color/border/error`; plus a
`High Contrast` mode on `PG ERD Color`. Direct Figma verification remains open.

### Code-side CSS tokens

`frontend/src/styles.css` previously had **no** `:root` token layer. This work
adds a minimal, non-duplicative token layer plus a High Contrast Mode
(`@media (prefers-contrast: more)`) aligned to the target Figma `High Contrast`
variable mode — applied to existing rules without changing default rendered
output:

```css
:root {
  --color-action-primary: #034ea2;       /* de-facto brand, previously hardcoded */
  --color-action-primary-hover: #023d80;
  --color-border-focus: #034ea2;
  --color-border-error: #b91c1c;
  --color-text-disabled: #9ca3af;
}

/* KRDS 선명한 화면 모드 (style_09) — target Figma "High Contrast" mode */
@media (prefers-contrast: more) {
  :root {
    --color-action-primary: #003a7a;
    --color-action-primary-hover: #001f40;
    --color-border-focus: #002d5c;
    --color-border-error: #8a0000;
    --color-text-disabled: #595959;
  }
}
```

**This intentionally does not replace or duplicate PR #406
(`codex/css-token-layer`)**, which proposes a much larger, complete
primitive+semantic token layer (~968 lines). As of 2026-07-03, that PR is open
but `BLOCKED` with `CHANGES_REQUESTED` from the automated OpenCode review body
because the model pool was exhausted; the GitHub checks, including
`opencode-review`, are green. Recommendation: re-run/dismiss that automated
review blocker or address any newly surfaced source-backed findings, then merge
#406 and reconcile its token names against the Figma `02. Tokens` page naming
convention.

## 3. Components — target Figma ↔ code mapping

| Target Figma component | Code / target status | Real dev component |
|---|---|---|
| PG ERD Button (06. Action) | Code: Primary/Secondary/Ghost/Danger + sm/md/lg; target Figma variants pending verification | **`frontend/src/components/Button.tsx`** — adopted in `AddTableModal` |
| PG ERD Breadcrumb (04. Navigation) | Code-only component | `frontend/src/components/Breadcrumb.tsx` — not adopted yet |
| PG ERD Pagination (04. Navigation) | Code-only partial: prev/next/current | `frontend/src/components/Pagination.tsx` — missing first/last/ellipsis and not adopted yet |
| PG ERD Input Field (10. Input) | Code-only component with helper/error wiring | `frontend/src/components/TextInput.tsx` — modal raw inputs still need adoption |
| PG ERD Checkbox (07. Selection) | Code-only native control wrapper | `frontend/src/components/Checkbox.tsx` — not adopted yet |
| PG ERD Radio (07. Selection) | Code-only native control wrapper | `frontend/src/components/Radio.tsx` — not adopted yet |
| PG ERD Select (07. Selection) | Code-only native control wrapper | `frontend/src/components/Select.tsx` — not adopted yet |
| PG ERD Table Node (05. Layout & Expression) | existing, documented | `frontend/src/erd/TableNode.tsx` (PK/NN `<abbr>` a11y from PR #417) |
| PG ERD Status Pill (05. Layout & Expression) | existing, documented | inline status/badge usages in table/edge UI |
| PG ERD Toolbar Button (06. Action) | existing, documented | toolbar buttons in `frontend/src/App.tsx` |
| PG ERD Share Export Modal (05. Layout & Expression) | existing, documented | `frontend/src/components/modals/ExportModal.tsx`, `useDialogAccessibility.ts` |
| PG ERD Spinner (08. Feedback) | Indeterminate + small/medium sizes | **`frontend/src/components/Spinner.tsx`** — adopted in auth loading |
| PG ERD Toast (13. Mobile) | Info/Success, no action | **`frontend/src/components/Toast.tsx`** — adopted in export copy feedback |

### Known gaps (target Figma / design inventory)

- Direct Figma verification: all target pages, variables, and component sets
  need inspection once Figma MCP is available.
- Dark mode: target `PG ERD Color` collection defines `Light` + `High Contrast`
  modes, but no dark mode.
- Snackbar remains a component gap. Pagination now has a partial code
  component, but it is not adopted and lacks the KRDS first/last/ellipsis
  behavior.
- Spinner and Toast are code-linked, but their Figma component sets still need
  direct verification when Figma MCP is available.

### Known gaps (code has it, Figma doesn't yet)

- Full keyboard-navigation flows for the ERD canvas (pan/zoom/select) are not
  modeled as a Figma interactive prototype — only the static "ERD Editor"
  screen exists on `15. Service Patterns`.
- Breadcrumb, Pagination, Checkbox, Radio, Select, and TextInput are currently
  code-only review components and need Figma variants plus product adoption
  before they can be marked Ready.

## 4. Accessibility

Grounded in real shipped work recorded for the target `16. Accessibility` page:
skip-link (`styles.css` `.skip-link`), global `:focus-visible` outline
(now token-driven via `--color-border-focus`), `noscript` fallback,
`role="alert"`/`aria-live` regions, accessible `Spinner`, `Toast`, and
accessibility PRs #417, #418, #309, #383. High Contrast Mode is now supported
via `@media (prefers-contrast: more)`.

## 5. Classification

**Design System Draft** — Foundation, tokens (incl. High Contrast Mode), a
repo-backed component inventory, basic/service patterns, accessibility
grounding, dev mapping and versioning all exist and are code-linked
(`Button.tsx`, `Spinner.tsx`, `Toast.tsx`, `--color-action-primary`,
`prefers-contrast`). But direct Figma verification/mutation, dark mode, several
applicable components (Snackbar, Tab, Textarea, Text Resize, Icon set), the
full CSS token layer (PR #406), and adoption of code-only components remain
open, so it is **not yet** a fully operable "Design System."

## 6. Follow-ups

1. Merge/re-review PR #406 (`codex/css-token-layer`) — currently open but
   blocked by automated review `CHANGES_REQUESTED` from model-pool exhaustion.
2. Extend `Button.tsx` adoption to remaining ad-hoc `<button>` call sites.
3. Finish/adopt Pagination first/last/ellipsis states; add Snackbar only when a
   UI needs undo/retry action; define a dark-mode variable mode only if product
   scope requires it.
4. Verify/create the Figma component sets once Figma MCP is available.
5. Model the ERD canvas keyboard-navigation flow as a Figma prototype.
6. Reconcile target Figma `color/action/primary` (`#2563eb`) to the code brand `#034ea2`.

## 7. Version notes

| Version | Date | Area | Change Type | Changed Item | Reason | Impact | Migration | Owner |
|---|---|---|---|---|---|---|---|---|
| v0.6 | 2026-07-03 | Component / Docs | Fixed | Button token mapping and Figma verification notes | Remove duplicate inline token path; avoid unverifiable Figma claims | Button styling uses shared `.btn` CSS tokens; docs distinguish code-linked vs Figma-verified | No migration; keep using `Button` | Dev |
| v0.5 | 2026-07-03 | Component / Mobile | Added | Toast dev component | Close KRDS Toast dev-mapping gap | Export copy feedback now has visual + screen-reader status | Use `Toast` for short action results without extra actions | Dev |
| v0.4 | 2026-07-03 | Component / Feedback | Added | Spinner dev component | Close KRDS Spinner dev-mapping gap | Auth loading now has visual + screen-reader status | Use `Spinner` for indeterminate waits | Dev |
