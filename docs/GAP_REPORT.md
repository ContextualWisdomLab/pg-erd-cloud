# KRDS Design System Gap Report

## Current Status

- **Classification:** Design System Draft.
- **Figma alignment:** Direct Figma MCP tools were unavailable in this
  environment, so page/component/variable creation could not be verified or
  completed from Codex. No placeholder Figma metadata file is used as a
  substitute.
- **Codebase sync:** `Button`, `Spinner`, and `Toast` are adopted in product
  flows. `TextInput`, `Checkbox`, `Radio`, `Select`, `Pagination`, and
  `Breadcrumb` exist as code-only review components and still need product
  adoption, Figma variants, and broader test coverage.

| Area | KRDS Reference | Issue | Severity | Required Action | Owner | Due |
|---|---|---|---|---|---|---|
| Foundation | Figma file | Direct Figma page/variable/component verification unavailable | Critical | Re-run with Figma MCP enabled; verify/create pages `00`-`19` and `99` | Design | TBD |
| Token | Design Token | Full primitive/semantic/component token layer is still partial in code | High | Reconcile `frontend/src/design-system/tokens.css`, `styles.css`, and PR #406 token names | Design/Dev | TBD |
| Component | Pagination | Code component lacks first/last and ellipsis states and is not adopted | Medium | Finish KRDS pagination behavior before product adoption | Dev | TBD |
| Component | Selection/Input wrappers | Checkbox, Radio, Select, TextInput are code-only review components | Medium | Add focused tests, adopt where used, and create Figma variants | Design/Dev | TBD |
| Component | Snackbar | No feedback-with-action component exists | Low | Add only when undo/retry action is needed | Design/Dev | TBD |
| Pattern | Service flows | ERD-specific visit/search/login flows are partial; 신청/정책 정보 확인 are N/A for product scope | Medium | Keep N/A items documented; prototype applicable ERD journeys when Figma is available | Design | TBD |
| Accessibility | Component matrix | Per-component keyboard/screen-reader/high-contrast matrix is incomplete | High | Extend `16. Accessibility` inventory and tests for adopted components | Design/Dev | TBD |

Severity follows the KRDS task definition: Critical for legal/accessibility or
task-blocking gaps, High for unusable core system parts, Medium for
consistency/usability gaps, Low for documentation/example gaps.
