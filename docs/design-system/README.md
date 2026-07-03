# PG ERD Design System

Status: **Design System Draft** (see classification rationale below)
Figma source of truth: `Product Design Kit` — file key `OTN0rBGtnVy0P7yq4Iv9Si`
Related docs: [`docs/ui-ux/README.md`](../ui-ux/README.md)

This document summarizes the Figma-based design system for pg-erd-cloud and
its current mapping to the real codebase. It exists so that engineers do not
need Figma access to understand what tokens/components exist, what is
missing, and which PRs are relevant.

For the **full KRDS traversal** (all 37+ components, 12 basic patterns, 5
service patterns) with per-item status and the machine-checkable Gap Report,
see [`krds-inventory.md`](./krds-inventory.md) — that file is the authoritative,
version-controlled mirror of the Figma inventory pages.

## 1. Figma page structure

The Figma file follows the KRDS-aligned **21-page** structure (components split
by KRDS category, plus a dedicated Gap Report):

| Page | Contents |
|---|---|
| `00. README` | Purpose, scope, adoption level, DS/UI-Kit criteria, naming/versioning rules |
| `01. Foundation` | Color, typography, shape/radius, layout, icon, elevation, **High Contrast Mode** |
| `02. Tokens` | Primitive / semantic / component token tiers + naming convention |
| `03. Components - Identity` | Masthead, identifier, header, footer (KRDS inventory) |
| `04. Components - Navigation` | Skip link, main/side menu, breadcrumb, pagination (inventory) |
| `05. Components - Layout & Expression` | Modal, Badge, Table Node + real `COMPONENT_SET`s (inventory) |
| `06. Components - Action` | **Button** + Toolbar Button `COMPONENT_SET`s (inventory) |
| `07. Components - Selection` | Radio, checkbox, select, tag, toggle (inventory) |
| `08. Components - Feedback` | Step indicator, spinner (inventory) |
| `09. Components - Help` | Tooltip, contextual help, coach mark, TTS (inventory) |
| `10. Components - Input` | **Input Field** `COMPONENT_SET` + text/date/file inputs (inventory) |
| `11. Components - Setting` | Language switcher, text resize (inventory) |
| `12. Components - Content` | Accessible media, hidden content (inventory) |
| `13. Components - Mobile` | Toast, snackbar, bottom sheet, back button (inventory) |
| `14. Basic Patterns` | KRDS 12 basic patterns inventory + real pattern frames |
| `15. Service Patterns` | KRDS 5 service patterns inventory + ERD core flow prototype |
| `16. Accessibility` | Grounded in shipped a11y work (skip-link, focus-visible, `<abbr>`, noscript) |
| `17. Dev Handoff` | Figma↔code component mapping + token gap analysis |
| `18. Version & Changelog` | Changelog (v0.1–v0.5), deprecation policy, classification |
| `19. Gap Report` | KRDS Area / Reference / Issue / Severity / Action / Owner / Due |
| `99. Archive / Deprecated` | Superseded/legacy exploration frames |

The 6 real `COMPONENT_SET`s are distributed to their KRDS categories: Button &
Toolbar Button → Action (06); Input Field → Input (10); Table Node, Status Pill
(Badge) & Share/Export Modal → Layout & Expression (05).

## 2. Tokens

### Figma variable collections (source of truth)

- `PG ERD Primitives` — 23 primitive colors (blue/slate/red/green/amber scales)
- `PG ERD Color` — 22 semantic colors, **two modes: `Light` + `High Contrast`** (선명한 화면 모드, KRDS style_09; 12 tokens overridden for high contrast). Dark mode still undefined — Gap.
- `PG ERD Spacing` — 11-step spacing scale
- `PG ERD Radius` — 4 radius values
- Text styles: `Heading/Large`, `Heading/Medium`, `Body/Default`, `Body/Strong`, `Caption`, `Mono/Small`
- Effect styles: `Shadow/Modal`, `Focus/Ring`

Three semantic variables were added to close variant gaps:
`color/border/focus`, `color/text/disabled`, `color/border/error`; plus a
`High Contrast` mode on `PG ERD Color`.

### Code-side CSS tokens

`frontend/src/styles.css` previously had **no** `:root` token layer. This work
adds a minimal, non-duplicative token layer plus a High Contrast Mode
(`@media (prefers-contrast: more)`) that mirrors the Figma `High Contrast`
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

/* KRDS 선명한 화면 모드 (style_09) — mirrors Figma "High Contrast" mode */
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

## 3. Components — Figma ↔ code mapping

| Figma component | Variants added/verified | Real dev component |
|---|---|---|
| PG ERD Button (06. Action) | Primary/Secondary/Ghost + Hover/Focus/Disabled | **`frontend/src/components/Button.tsx`** (new) — adopted in `AddTableModal` |
| PG ERD Input Field (10. Input) | + Error, Read-only states | modal form inputs across `frontend/src/components/modals/*.tsx` |
| PG ERD Table Node (05. Layout & Expression) | existing, documented | `frontend/src/erd/TableNode.tsx` (PK/NN `<abbr>` a11y from PR #417) |
| PG ERD Status Pill (05. Layout & Expression) | existing, documented | inline status/badge usages in table/edge UI |
| PG ERD Toolbar Button (06. Action) | existing, documented | toolbar buttons in `frontend/src/App.tsx` |
| PG ERD Share Export Modal (05. Layout & Expression) | existing, documented | `frontend/src/components/modals/ExportModal.tsx`, `useDialogAccessibility.ts` |
| PG ERD Spinner (08. Feedback) | Indeterminate + small/medium sizes | **`frontend/src/components/Spinner.tsx`** — adopted in auth loading |
| PG ERD Toast (13. Mobile) | Info/Success, no action | **`frontend/src/components/Toast.tsx`** — adopted in export copy feedback |

### Known gaps (Figma has it, code doesn't)

- Dark mode: Figma `PG ERD Color` collection defines `Light` + `High Contrast`
  modes, but no dark mode.
- Snackbar / Pagination components are inventoried as Gaps (see
  [`krds-inventory.md`](./krds-inventory.md) §4). Spinner and Toast are
  code-linked, but their Figma component sets still need direct verification
  when Figma MCP is available.

### Known gaps (code has it, Figma doesn't yet)

- Full keyboard-navigation flows for the ERD canvas (pan/zoom/select) are not
  modeled as a Figma interactive prototype — only the static "ERD Editor"
  screen exists on `15. Service Patterns`.

## 4. Accessibility

Grounded in real shipped work referenced on the `16. Accessibility` Figma
page: skip-link (`styles.css` `.skip-link`), global `:focus-visible` outline
(now token-driven via `--color-border-focus`), `noscript` fallback,
`role="alert"`/`aria-live` regions, accessible `Spinner`, `Toast`, and
accessibility PRs #417, #418, #309, #383. High Contrast Mode is now supported
via `@media (prefers-contrast: more)`.

## 5. Classification

**Design System Draft** — Foundation, tokens (incl. High Contrast Mode), a real
component library (6 sets), basic/service patterns, accessibility grounding, dev
mapping and versioning all exist and are now code-linked (`Button.tsx`,
`Spinner.tsx`, `Toast.tsx`, `--color-action-primary`, `prefers-contrast`). But
dark mode, several applicable components (Snackbar, Pagination), the full CSS
token layer (PR #406), and direct Figma verification for the Spinner/Toast
component sets remain open, so it is **not yet** a fully operable "Design
System."

## 6. Follow-ups

1. Merge/re-review PR #406 (`codex/css-token-layer`) — currently open but
   blocked by automated review `CHANGES_REQUESTED` from model-pool exhaustion.
2. Extend `Button.tsx` adoption to remaining ad-hoc `<button>` call sites.
3. Add Snackbar and Pagination components; define a dark-mode variable mode.
4. Verify/create the Figma Spinner and Toast component sets once Figma MCP is available.
5. Model the ERD canvas keyboard-navigation flow as a Figma prototype.
6. Reconcile Figma `color/action/primary` (`#2563eb`) to the code brand `#034ea2`.

## 7. Version notes

| Version | Date | Area | Change Type | Changed Item | Reason | Impact | Migration | Owner |
|---|---|---|---|---|---|---|---|---|
| v0.5 | 2026-07-03 | Component / Mobile | Added | Toast dev component | Close KRDS Toast dev-mapping gap | Export copy feedback now has visual + screen-reader status | Use `Toast` for short action results without extra actions | Dev |
| v0.4 | 2026-07-03 | Component / Feedback | Added | Spinner dev component | Close KRDS Spinner dev-mapping gap | Auth loading now has visual + screen-reader status | Use `Spinner` for indeterminate waits | Dev |
