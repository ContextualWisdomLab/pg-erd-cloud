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
| Component | Snackbar | No feedback-with-action component exists | Low | Add only when undo/retry action is needed | Design/Dev | TBD |
| Pattern | Service flows | **Resolved** — 방문/검색/로그인 all now have real Figma prototype reactions (`setReactionsAsync`, ON_CLICK/AFTER_TIMEOUT → NAVIGATE), not just visual connector lines; Login screens (Loading/Error/Success) are grounded in the real `AuthGate` branch in `App.tsx`. 신청/정책 정보 확인 remain N/A for product scope | N/A | None | – | ✔ |
| Component | Toolbar Button (Action) | `PG ERD Toolbar Button` Icon/Format kinds exist but aren't cross-referenced with the new `PG ERD Icon` set | Low | Swap Toolbar Button's icon slots to use `PG ERD Icon` instances via INSTANCE_SWAP | Design | TBD |
| Accessibility | Component matrix | Per-component keyboard/screen-reader/high-contrast matrix is incomplete; automated WCAG 4.5:1 contrast reporting doesn't exist | Medium | Extend `06. Accessibility` inventory and tests for adopted components | Design/Dev | TBD |

Severity follows the KRDS task definition: Critical for legal/accessibility or
task-blocking gaps, High for unusable core system parts, Medium for
consistency/usability gaps, Low for documentation/example gaps.
