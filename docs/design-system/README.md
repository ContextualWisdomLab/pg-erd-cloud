# PG ERD Design System

Status: **Design System Draft** (see classification rationale below)
Target Figma file: `Product Design Kit` — file key `OTN0rBGtnVy0P7yq4Iv9Si`
Related docs: [`docs/ui-ux/README.md`](../ui-ux/README.md)

This document summarizes the repo-backed KRDS design-system inventory for
pg-erd-cloud and its current mapping to the real codebase. **Update
(2026-07-03):** Direct Figma MCP tools (`use_figma`, `get_screenshot`,
`get_metadata`) were confirmed working in this environment and used to
directly inspect and mutate the target file. See `docs/GAP_REPORT.md` and
`docs/figma-meta.json` for the verified state and object counts. The "target"
language below predates that verification; items confirmed built are noted
inline, everything else should still be treated as target structure.

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

The repo mirror records 6 pre-existing component-set targets distributed to
their KRDS categories: Button & Toolbar Button → Action (06); Input Field →
Input (10); Table Node, Status Pill (Badge) & Share/Export Modal → Layout &
Expression (05) — all confirmed present via Figma MCP on 2026-07-03. 8 more
were added the same session: Checkbox, Radio, Select, Tag → Selection (07);
Pagination Item, Breadcrumb Item → Navigation (04); Spinner → Feedback (08);
Toast → Mobile (13).

## 2. Tokens

### Figma variable collections (verified present, 2026-07-03)

- `PG ERD Primitives` — 23 primitive colors (blue/slate/red/green/amber scales)
- `PG ERD Color` — 22 semantic colors, **two modes: `Light` + `High Contrast`** (선명한 화면 모드, KRDS style_09; 12 tokens overridden for high contrast). Dark mode still undefined — Gap. `color/action/primary` and `color/action/primary-hover` (Light mode) were reconciled 2026-07-03 from an unrelated aliased blue to the code brand `#034ea2`/`#023d80`.
- `PG ERD Spacing` — 11-step spacing scale
- `PG ERD Radius` — 4 radius values
- Text styles: `Heading/Large`, `Heading/Medium`, `Body/Default`, `Body/Strong`, `Caption`, `Mono/Small`
- Effect styles: `Shadow/Modal`, `Focus/Ring`

The repo mirror records three semantic variables that close variant gaps:
`color/border/focus`, `color/text/disabled`, `color/border/error`; plus the
`High Contrast` mode on `PG ERD Color`. All confirmed bound to real component
fills/strokes (not hardcoded) via Figma MCP inspection.

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
| PG ERD Button (06. Action) | Code: Primary/Secondary/Ghost/Danger + sm/md/lg; Figma set verified (Style×State incl. Hover/Focus) | **`frontend/src/components/Button.tsx`** — adopted in `AddTableModal` |
| PG ERD Breadcrumb Item (04. Navigation) | Code-only component; Figma set added 2026-07-03 (Design Only) | `frontend/src/components/Breadcrumb.tsx` — not adopted yet |
| PG ERD Pagination Item (04. Navigation) | Code-only partial: prev/next/current; Figma set added 2026-07-03 | `frontend/src/components/Pagination.tsx` — missing first/last/ellipsis and not adopted yet |
| PG ERD Input Field (10. Input) | Code-only component with helper/error wiring; Figma set verified (5 states) | `frontend/src/components/TextInput.tsx` — modal raw inputs still need adoption |
| PG ERD Checkbox (07. Selection) | Code-only native control wrapper; Figma set added 2026-07-03 (6 states incl. Indeterminate/Focus) | `frontend/src/components/Checkbox.tsx` — not adopted yet |
| PG ERD Radio (07. Selection) | Code-only native control wrapper; Figma set added 2026-07-03 (5 states incl. Focus) | `frontend/src/components/Radio.tsx` — not adopted yet |
| PG ERD Select (07. Selection) | Code-only native control wrapper; Figma set added 2026-07-03 (5 states incl. Expanded dropdown) | `frontend/src/components/Select.tsx` — not adopted yet |
| PG ERD Tag (07. Selection) | No dedicated code component; Figma set added 2026-07-03 (4 tones) | inline `businessGroups` tag styling in `App.tsx` |
| PG ERD Table Node (05. Layout & Expression) | existing, verified | `frontend/src/erd/TableNode.tsx` (PK/NN `<abbr>` a11y from PR #417) |
| PG ERD Status Pill (05. Layout & Expression) | existing, verified | inline status/badge usages in table/edge UI |
| PG ERD Toolbar Button (06. Action) | existing, verified | toolbar buttons in `frontend/src/App.tsx` |
| PG ERD Share Export Modal (05. Layout & Expression) | existing, verified | `frontend/src/components/modals/ExportModal.tsx`, `useDialogAccessibility.ts` |
| PG ERD Spinner (08. Feedback) | Small/Medium sizes; Figma set added 2026-07-03 | **`frontend/src/components/Spinner.tsx`** — adopted in auth loading |
| PG ERD Toast (13. Mobile) | Info/Success adopted in code; Figma set added 2026-07-03 with 2 more Design-Only tones (Warning/Danger) | **`frontend/src/components/Toast.tsx`** — adopted in export copy feedback |

### Known gaps (design inventory)

- Dark mode: `PG ERD Color` collection defines `Light` + `High Contrast`
  modes, but no dark mode.
- Snackbar remains a component gap. Pagination now has a Figma component set
  and a partial code component, but neither is adopted and the code lacks the
  KRDS first/last/ellipsis behavior.
- `PG ERD Icon` (5 icons, token-bound) exists as of 2026-07-03, but no code
  Icon component exists to adopt it against — product still uses inline
  SVG/text labels.
- All 3 applicable service patterns (방문/검색/로그인) now have real Figma
  prototype connections (`setReactionsAsync`, added 2026-07-03) — previously
  방문/검색 only had visual connector lines and 로그인 had no screens at all.

### Known gaps (code has it, Figma doesn't yet)

- Full keyboard-navigation flows for the ERD canvas (pan/zoom/select) are not
  modeled as a Figma interactive prototype — only the static "ERD Editor"
  screen exists on `15. Service Patterns`.
- Breadcrumb, Pagination, Checkbox, Radio, Select, and TextInput are currently
  code-only review components; Figma variants now exist for all of them
  (added 2026-07-03), but product adoption in the actual UI is still open.

## 4. Accessibility

Grounded in real shipped work recorded for the target `16. Accessibility` page:
skip-link (`styles.css` `.skip-link`), global `:focus-visible` outline
(now token-driven via `--color-border-focus`), `noscript` fallback,
`role="alert"`/`aria-live` regions, accessible `Spinner`, `Toast`, and
accessibility PRs #417, #418, #309, #383. High Contrast Mode is now supported
via `@media (prefers-contrast: more)`.

## 5. Classification

**Design System Draft** — Foundation (incl. an Icon set), tokens (incl. High
Contrast Mode), a repo-backed component inventory, basic/service patterns
(all 3 applicable service patterns now have real prototype connections),
accessibility grounding, dev mapping and versioning all exist, are verified
directly in Figma (not just asserted, as of 2026-07-03), and are code-linked
(`Button.tsx`, `Spinner.tsx`, `Toast.tsx`, `--color-action-primary`,
`prefers-contrast`). Still open: dark mode, several applicable components
(Snackbar, Tab, Textarea, Text Resize), the full CSS token layer (PR #406),
and adoption of the newly-Figma'd components into product UI — so it is
**not yet** a fully operable "Design
System."

## 6. Follow-ups

1. Merge/re-review PR #406 (`codex/css-token-layer`) — currently open but
   blocked by automated review `CHANGES_REQUESTED` from model-pool exhaustion.
2. Extend `Button.tsx` adoption to remaining ad-hoc `<button>` call sites.
3. Finish/adopt Pagination first/last/ellipsis states; add Snackbar only when a
   UI needs undo/retry action; define a dark-mode variable mode only if product
   scope requires it.
4. Model the ERD canvas keyboard-navigation flow as a Figma prototype.
5. Decide whether a code Icon component is worth building against the new
   `PG ERD Icon` Figma set, or whether inline SVG remains fine for this
   product's scope.

## 7. Version notes

| Version | Date | Area | Change Type | Changed Item | Reason | Impact | Migration | Owner |
|---|---|---|---|---|---|---|---|---|
| v0.8 | 2026-07-03 | Foundation / Service Pattern | Added | `PG ERD Icon` set (5 icons) + size grid; `PG ERD Login Flow` (Loading/Error/Success); real `setReactionsAsync` prototype connections on all 3 applicable service patterns | Close the style_06 Icon gap and the missing Login-flow gap; upgrade 방문/검색 from visual-line-only connectors (not real prototype interactions) to real ones | KRDS Foundation/Service Pattern coverage now has no missing applicable items; remaining gaps are code-adoption, not Figma-object gaps | No code migration; Figma-only + docs | Design |
| v0.7 | 2026-07-03 | Component / Docs | Added | 8 Figma Component Sets (Checkbox, Radio, Select, Tag, Pagination Item, Breadcrumb Item, Spinner, Toast) + brand color reconciliation | Close the Figma-side gap `krds-inventory.md` had flagged for these; direct Figma MCP access confirmed working this session | These components now have real, variant-bound Figma Component Sets, not just code; `color/action/primary`/`-hover` now match code brand | No code migration; Figma-only + docs | Design/Dev |
| v0.6 | 2026-07-03 | Component / Docs | Fixed | Button token mapping and Figma verification notes | Remove duplicate inline token path; avoid unverifiable Figma claims | Button styling uses shared `.btn` CSS tokens; docs distinguish code-linked vs Figma-verified | No migration; keep using `Button` | Dev |
| v0.5 | 2026-07-03 | Component / Mobile | Added | Toast dev component | Close KRDS Toast dev-mapping gap | Export copy feedback now has visual + screen-reader status | Use `Toast` for short action results without extra actions | Dev |
| v0.4 | 2026-07-03 | Component / Feedback | Added | Spinner dev component | Close KRDS Spinner dev-mapping gap | Auth loading now has visual + screen-reader status | Use `Spinner` for indeterminate waits | Dev |
