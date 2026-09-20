# Live Figma Design QA

Checked: 2026-08-09

## Result

No actionable P0/P1 implementation defect remains in the code-level contract checks. Final visual sign-off is blocked because the approved cloud browser rejects the sandbox-isolated loopback preview (`ERR_BLOCKED_BY_CLIENT` on the 2026-08-09 retry), so a same-viewport source/implementation screenshot comparison could not be produced. Historical 2026-07-02 captures were not reused as current evidence.

`final result: blocked`

## Authoritative Source

The node inventory, precedence, Figma API limitation, and audited code SHAs are
owned by [`docs/ui-ux/figma-contract.md`](docs/ui-ux/figma-contract.md). This QA
record intentionally does not duplicate that changing contract. The deleted
ShareExport node `29:143` and committed 2026-07-02 captures remain historical
evidence only.

## Verified Contracts

- The desktop ERDEditor follows the concrete 1440px frame split: 300px navigation, 850px canvas, and 290px properties inspector. At 767px the shell and inspector stack.
- The compact toolbar follows the live order and keeps search in the properties inspector.
- Shared Figma tokens cover colors, type, spacing, radius, effects, component sizes, modal sizes, responsive breakpoint, and disabled opacity. Inter 400/500/700 is bundled first, with bundled Noto Sans KR Variable covering Korean glyphs before the system fallback. Computed-style tests verify the concrete screen geometry and responsive rules.
- React Flow controls, minimaps, backgrounds, connection handles, and relationship lines follow the system light/dark mode. Control, handle, and edge boundaries use dedicated semantic tokens that retain at least 3:1 contrast against their light/dark surfaces.
- ShareExport keeps the live Korean share-link and DDL hierarchy, uses a fixed footer for DDL copy, and keeps existing extra export formats in a collapsed disclosure.
- All editor dialogs use one labelled `aria-modal` shell with initial focus, Tab/Shift+Tab containment, Escape close, focus return, neutral structural wrappers, and an explicit backdrop policy, following the [WAI-ARIA modal dialog pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/).
- Group colors use a keyboard-operable radio-group model with roving `tabindex`; destructive mutations prompt once at the application boundary.
- React Flow selection uses the controlled selection callback, exposes keyboard-selected relationships in the Properties inspector, and clears stale selection when the graph changes, consistent with [React Flow accessibility guidance](https://reactflow.dev/learn/advanced-use/accessibility).
- The public `/share/{id}` route renders successful API snapshots as a read-only ERD with no interaction unlock control, keeps server errors generic, and does not pre-escape React text. The export modal explains server expiry and owner API revocation while disclosing that this UI has no revoke button.

## Resolved Figma Conflicts

- `layout/sidebar-width` is 360px, but the concrete ERDEditor screen is explicitly 300/850/290. Screen geometry wins for that screen; the general 360px variable remains in the token inventory.
- ShareExport is drawn at 720px, but Developer Handoff explicitly says modal widths map to `modal/*` variables. The implementation therefore uses `modal/export-width` at 500px.
- Figma dark inverse text and success-state color pairs fall below the [WCAG 2.2 normal-text contrast requirement](https://www.w3.org/TR/WCAG22/#contrast-minimum). The implementation uses audited inverse and success text overrides in light and dark modes.
- Figma default/subtle borders and React Flow edge defaults fall below the [WCAG 2.2 non-text contrast requirement](https://www.w3.org/TR/WCAG22/#non-text-contrast) when used as the sole control, handle, or relationship-edge boundary. Dedicated light/dark control and focus-border overrides provide at least 3:1 contrast while structural dividers retain the supplied tokens.
- Auth text, narrow modal footers, and the oversized ShareExport showcase are treated as documented Figma defects: implementation allows wrapping, keeps actions visible, and remains scroll-safe.

## Verification Evidence

- Frontend unit and interaction tests cover screen navigation, editor selection, modal actions, public sharing, API parsing, exports, accessibility behavior, Figma tokens, and responsive CSS contracts.
- TypeScript typecheck, production build, diff whitespace check, and V8 coverage are required before handoff.
- Visual source inspection used the live Figma nodes above. Implementation screenshot comparison remains the only blocked gate.

## Required Follow-up

Run the approved browser against a reachable preview at desktop `1440×900` and mobile `390×844`, capture the same states as the live source nodes, combine each source/implementation pair, and update this file only after visible spacing, typography, overflow, focus, and state differences have been reviewed.
