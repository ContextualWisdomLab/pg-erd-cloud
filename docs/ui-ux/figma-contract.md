# Live Figma Contract

Last checked: 2026-08-09

This file records the live source of truth for Cloud ERD implementation work.
Use it before the historical PNGs or QA captures in this directory.

## Precedence

1. Concrete live `Screen Templates` and `Implementation Contracts` in the authoritative Figma file.
2. Explicit Developer Handoff mappings and shared component contracts. When a concrete screen and a free-standing variable differ, use the concrete screen unless the handoff explicitly maps that property to the variable.
3. Current frontend behavior where Figma explicitly documents it as an intentional extension.
4. Committed QA captures under `docs/ui-ux/qa`.
5. Legacy reference images `01-login-screen.png` through `09-share-export-modal.png`.

The former share/export node `29:143` no longer exists. Do not use it as a live Figma reference.

## Authoritative file

- File key: `csnpEEJfmqFWB0vNUoTkWA`
- Screen Templates: `7:9`
- Button: `21:2`
- Form Controls: `24:2`
- Badges and Swatches: `28:2`
- ModalShell: `29:2`
- TableNode: `32:2`
- Editor Controls: `35:2`
- Product Organisms: `36:2`
- Developer Handoff: `39:3`
- Implementation Contracts: `45:2`

The supplemental file `OTN0rBGtnVy0P7yq4Iv9Si` currently contains an empty page and conflicting variables. It is not authoritative.

## Screen nodes

| Screen | Node | Target frame |
| --- | --- | --- |
| AuthGate | `37:2` | 390×720 |
| Dashboard | `37:10` | 1440×900 |
| ProjectList | `37:62` | 390×720 |
| DiagramList | `37:88` | 390×720 |
| ERDEditor | `37:114` | 1440×900 |
| AddTableModal | `37:253` | 900×640 |
| RelationshipSettingsModal | `37:271` | 900×640 |
| ShareExportModal | `130:232` | 900×640 |
| GroupModal | `130:259` | 900×640 |
| CardinalityModal | `130:285` | 900×640 |
| EditTableModal | `130:313` | 900×640 |

## Implementation rules

- Desktop ERDEditor screen: 300px navigation, 850px canvas, and 290px properties panel at 1440px.
- Compact canvas toolbar order: `↔`, `↶`, `+`, `◇`, `#`, `SQL`, `IMG`, `UML`, `{}`, `↗`.
- Modal product copy and fields come from the concrete Korean screen nodes. `ModalShell` variants define shared layout and behavior only.
- Modal widths follow the explicit Developer Handoff mapping to `modal/*` variables: add table 300px, relationship 320px, share/export 500px, group 680px, cardinality 760px, and edit table 800px.
- Every dialog must provide a labelled modal role, initial focus, focus trap, Escape close, focus return, and an explicit backdrop-close policy.
- Use semantic `--pg-*` variables for color, spacing, radius, type, sizing, and effects. Light and dark modes remain available.
- Bundle the Figma Inter regular/medium/bold weights and place the Figma sans token first in the global application stack.
- At 767px and below, the application shell and editor inspector must stack without horizontal page overflow.
- User content is rendered as React text, not pre-encoded HTML or raw HTML.

## Intentional extensions

- DBML, Prisma, and data-dictionary exports remain available under the collapsed “기타 산출물” disclosure. The default share/export view follows the live Figma share-link and DDL sections.
- The public share URL uses `/share/{id}` and renders successful public API snapshots as a read-only ERD. The backend `/api/share/{id}` route remains the data endpoint, and the product copy must disclose that anyone with the bearer link can view it while expiry/revocation is unavailable.
- Auth loading and authentication-required states reuse the AuthGate card tokens because the live file defines only the idle login state and the repository does not yet provide an OIDC login redirect UI.

## Known Figma defects not to reproduce

- Auth description text is too short for its copy and overlaps the Email label; implementation must allow wrapping and auto height.
- Narrow ModalShell footer examples clip actions; implementation must keep every action visible.
- The ShareExport frame is taller than its 640px showcase frame; implementation must be scroll-safe.
- The general `layout/sidebar-width` variable is 360px, while the concrete ERDEditor screen is explicitly 300/850/290. The screen-scoped implementation follows the concrete screen geometry and retains the general variable in the token inventory.
- The ShareExport frame is 720px wide, while the Developer Handoff explicitly requires modal widths to map to `modal/*`; the implementation therefore uses `modal/export-width` at 500px.
- Dark-mode `color/text/inverse` resolves to dark text over the blue primary action and does not meet the normal-text contrast requirement. The implementation uses white action text as an audited accessibility override.
- The supplied success text/surface pair is below 4.5:1 in light mode and substantially lower in dark mode. The implementation uses darker light-theme and lighter dark-theme success text as audited accessibility overrides.
