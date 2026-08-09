# Live Figma Design QA

Checked: 2026-08-09

## Result

No actionable P0/P1 implementation defect remains in the code-level contract checks. Final visual sign-off is blocked because the approved cloud browser could not reach the sandbox-isolated local Vite server (`ERR_CONNECTION_REFUSED`), so a same-viewport source/implementation screenshot comparison could not be produced. Historical 2026-07-02 captures were not reused as current evidence.

`final result: blocked`

## Authoritative Source

- Figma file: `csnpEEJfmqFWB0vNUoTkWA`.
- Screen templates: AuthGate `37:2`, Dashboard `37:10`, ProjectList `37:62`, DiagramList `37:88`, ERDEditor `37:114`, AddTable `37:253`, Relationship `37:271`, ShareExport `130:232`, Group `130:259`, Cardinality `130:285`, and EditTable `130:313`.
- Developer Handoff: `39:3`; Implementation Contracts: `45:2`.
- The deleted ShareExport node `29:143` and committed 2026-07-02 captures are historical evidence only.

## Verified Contracts

- The desktop ERDEditor follows the concrete 1440px frame split: 300px navigation, 850px canvas, and 290px properties inspector. At 767px the shell and inspector stack.
- The compact toolbar follows the live order and keeps search in the properties inspector.
- Shared Figma tokens cover colors, type, spacing, radius, effects, component sizes, modal sizes, responsive breakpoint, and disabled opacity. Inter 400/500/700 is bundled and placed first in the application font stack. Computed-style tests verify the concrete screen geometry and responsive rules.
- React Flow controls, minimaps, backgrounds, and connection handles follow the system light/dark mode and the semantic handle tokens.
- ShareExport keeps the live Korean share-link and DDL hierarchy, uses a fixed footer for DDL copy, and keeps existing extra export formats in a collapsed disclosure.
- All editor dialogs use one labelled `aria-modal` shell with initial focus, Tab/Shift+Tab containment, Escape close, focus return, neutral structural wrappers, and an explicit backdrop policy, following the [WAI-ARIA modal dialog pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/).
- Group colors use a keyboard-operable radio-group model with roving `tabindex`; destructive mutations prompt once at the application boundary.
- React Flow selection uses the controlled selection callback, and stale selection is cleared when the graph changes, consistent with [React Flow accessibility guidance](https://reactflow.dev/learn/advanced-use/accessibility).
- The public `/share/{id}` route renders successful API snapshots as a read-only ERD with no interaction unlock control, keeps server errors generic, and does not pre-escape React text. The export modal warns that bearer links currently have no expiry or revocation control.

## Resolved Figma Conflicts

- `layout/sidebar-width` is 360px, but the concrete ERDEditor screen is explicitly 300/850/290. Screen geometry wins for that screen; the general 360px variable remains in the token inventory.
- ShareExport is drawn at 720px, but Developer Handoff explicitly says modal widths map to `modal/*` variables. The implementation therefore uses `modal/export-width` at 500px.
- Figma dark inverse text and success-state color pairs fall below the [WCAG 2.2 normal-text contrast requirement](https://www.w3.org/TR/WCAG22/#contrast-minimum). The implementation uses audited inverse and success text overrides in light and dark modes.
- Auth text, narrow modal footers, and the oversized ShareExport showcase are treated as documented Figma defects: implementation allows wrapping, keeps actions visible, and remains scroll-safe.

## Verification Evidence

- Frontend unit and interaction tests cover screen navigation, editor selection, modal actions, public sharing, API parsing, exports, accessibility behavior, Figma tokens, and responsive CSS contracts.
- TypeScript typecheck, production build, diff whitespace check, and V8 coverage are required before handoff.
- Visual source inspection used the live Figma nodes above. Implementation screenshot comparison remains the only blocked gate.

## Required Follow-up

Run the approved browser against a reachable preview at desktop `1440×900` and mobile `390×844`, capture the same states as the live source nodes, combine each source/implementation pair, and update this file only after visible spacing, typography, overflow, focus, and state differences have been reviewed.
