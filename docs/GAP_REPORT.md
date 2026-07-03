# KRDS Design System Gap Report

## Current Status

- **Classification:** Design System Draft.
- **Figma alignment:** Correction (2026-07-03) — the previous entry above
  (written earlier the same day) claimed "no Figma MCP tool has ever been
  available in this environment." That claim is **also false**, and this time
  it was verified rather than asserted: in this session the Figma MCP
  (`use_figma`/`get_metadata`/`get_screenshot`, via the Figma plugin server)
  worked against the real target file `OTN0rBGtnVy0P7yq4Iv9Si` and was used to
  read and mutate it directly. `get_metadata` was inspected first (which
  showed only a stub page and caused an earlier false start of duplicate
  pages, since reverted), then `use_figma` — which reflects the true live
  file — showed the file already contained a mature, pre-existing design
  system: 20 pages, 4 variable collections (`PG ERD Primitives/Color/Spacing/
  Radius`, with `Light`+`High Contrast` modes on Color), 6 text styles, 2
  effect styles, and real Component Sets for Button, Toolbar Button, Input
  Field, Table Node, Status Pill, and Share Export Modal — none of which
  either prior GAP_REPORT entry acknowledged. This session verified that
  state with `get_screenshot` (not just claimed it), then:
  - Built the 8 Component Sets `krds-inventory.md` had marked Review/Gap:
    Checkbox, Radio, Select, Tag, Pagination Item, Breadcrumb Item, Spinner,
    Toast — each with real Auto Layout, variant states (incl. Focus/Error/
    Disabled), and variables bound (not hardcoded values).
  - Reconciled `color/action/primary` and `color/action/primary-hover`
    (Light mode) from an unrelated aliased blue to the actual code brand
    `#034ea2`/`#023d80` — this was a real, previously-logged Gap.
  - Built the first real instance-composed Basic Pattern board (입력폼/테이블
    추가: Default/Error/Success) using live component instances, not text —
    the pre-existing "14. Basic Patterns" content was thorough but 100% text/
    documentation with zero component instances.
  - Updated the file's own `19. Gap Report`/`18. Version & Changelog`/`07. Dev
    Handoff` pages in place to reflect what changed.
  See `docs/figma-meta.json` for verified object counts. `tools/figma-plugin/
  krds-design-system/` (the manual-plugin fallback built when MCP genuinely
  wasn't available in an earlier session) is no longer the applicable path —
  MCP access works now — but is left in place rather than deleted.
- **Pass 2 (same day):** Traversed the real KRDS style/component/global/service
  pages via `WebFetch` and confirmed `krds-inventory.md`'s existing scoping
  (55 components, 11 basic patterns, 5 service patterns) matches the official
  source. Added a Figma `PG ERD Icon` set (closing the style_06 Foundation
  gap), a real Login Flow grounded in the `AuthGate` code, and upgraded the
  Core Flow's visual-only connector lines to real `setReactionsAsync`
  prototype connections.
- **Pass 3 (same day):** Built the 2 Component Sets the completion criteria
  explicitly require and that were still missing — a generic `PG ERD Modal`
  (Informational/Confirm/Alert/Fullscreen) and `PG ERD Header` — plus Footer,
  Tab, Snackbar, Text Area, Link, and Tooltip. Built 2 more real
  instance-composed pattern boards (확인/Confirmation, 목록 탐색/List
  Navigation with Default/Loading/Empty/Error). Rebuilt the Accessibility Lab
  page around 7 real UI objects (focus ring gallery, tab order demo, form
  error association, modal focus trap demo, skip link demo, text resize
  stress test, touch target demo) instead of checklist text. Added a
  `01. KRDS Source Inventory` table. **Found a real, generally-applicable
  Figma Plugin API bug in the process:** TEXT component properties sharing a
  name across variants in one Component Set collapse to ONE default value at
  the set level — new instances silently show the wrong variant's text unless
  `setProperties()` is called explicitly per instance. This was caught (and
  fixed) in this session's own Confirmation/List Navigation pattern boards;
  logged as a new Gap Report row in the Figma file itself so it isn't
  forgotten for older or future instances.
- **Pass 4 (same day, via `/loop`):** Closed the two remaining self-audit
  gaps from the final report: added 3 real Figma Grid Styles (`PG ERD Grid /
  Desktop` 1200px-12col, `Tablet` 768px-8col, `Mobile` 360px-4col) — since
  layout grids don't render in exported screenshots, also added visible
  column-overlay rectangles so the grid is a genuine visual specimen, not
  just an invisible property. Added the file's first Boolean (`Icon`) and
  Instance Swap (`Leading Icon`) component properties, added directly to the
  `PG ERD Button` `ComponentSetNode` (confirmed the Plugin API allows this
  post-hoc, contrary to the "add before combineAsVariants" guidance for
  per-variant properties) and demonstrated working via a live `Icon=true`
  instance referencing `PG ERD Icon/Check`.
- **Codebase sync:** `Button`, `Spinner`, and `Toast` are adopted in product
  flows. `TextInput`, `Checkbox`, `Radio`, `Select`, `Pagination`, and
  `Breadcrumb` exist as code-only review components and still need product
  adoption and broader test coverage. Figma variants now exist for all of
  them (see above).

| Area | KRDS Reference | Issue | Severity | Required Action | Owner | Due |
|---|---|---|---|---|---|---|
| Token | Design Token | Full primitive/semantic/component token layer is still partial in code | High | Reconcile `frontend/src/design-system/tokens.css`, `styles.css`, and PR #406 token names | Design/Dev | TBD |
| Component | Pagination | Code component lacks first/last and ellipsis states and is not adopted; Figma `PG ERD Pagination Item` now exists | Medium | Finish KRDS pagination behavior before product adoption | Dev | TBD |
| Component | Selection/Input wrappers | Checkbox, Radio, Select, TextInput are code-only review components; Figma variants now exist for all | Medium | Add focused tests, adopt where used | Design/Dev | TBD |
| Component | Toast | Figma `PG ERD Toast` now has 4 tones (Info/Success/Warning/Danger); only Info/Success are adopted in code | Low | Add Warning/Danger tone support to `Toast.tsx` if/when needed | Dev | TBD |
| Component | Snackbar | Figma `PG ERD Snackbar` now exists (Design Only); no code component | Low | Add code component only when undo/retry action is needed | Design/Dev | TBD |
| Component | Modal/Header/Footer/Tab/Text Area/Link/Tooltip | Figma Component Sets now exist for all 7 (required by completion criteria or logged Review/Gap items); code has no shared Modal component, no global Header/Footer, no tablist semantics, no Textarea/Link/Tooltip components | Medium | Product/dev decision needed on which of these are worth building in code vs. staying Figma-only for this B2B tool | Design/Dev | TBD |
| Process | Shared TEXT property defaults | Figma Plugin API gotcha: same-named TEXT properties across variants in one Component Set share one default; instances need explicit `setProperties()` | Medium | Audit any pre-existing multi-variant instances (Share Export Modal, Status Pill, Table Node) for the same silent-wrong-text issue | Design | TBD |
| Pattern | Service flows | **Resolved** — 방문/검색/로그인 all now have real Figma prototype reactions (`setReactionsAsync`, ON_CLICK/AFTER_TIMEOUT → NAVIGATE), not just visual connector lines; Login screens (Loading/Error/Success) are grounded in the real `AuthGate` branch in `App.tsx`. 신청/정책 정보 확인 remain N/A for product scope | N/A | None | – | ✔ |
| Component | Toolbar Button (Action) | `PG ERD Toolbar Button` Icon/Format kinds exist but aren't cross-referenced with the new `PG ERD Icon` set | Low | Swap Toolbar Button's icon slots to use `PG ERD Icon` instances via INSTANCE_SWAP | Design | TBD |
| Accessibility | Component matrix | Per-component keyboard/screen-reader/high-contrast matrix is incomplete; automated WCAG 4.5:1 contrast reporting doesn't exist | Medium | Extend `06. Accessibility` inventory and tests for adopted components | Design/Dev | TBD |

Severity follows the KRDS task definition: Critical for legal/accessibility or
task-blocking gaps, High for unusable core system parts, Medium for
consistency/usability gaps, Low for documentation/example gaps.
