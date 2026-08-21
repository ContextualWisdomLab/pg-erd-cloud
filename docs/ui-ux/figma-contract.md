# Live Figma Contract

Last checked: 2026-08-21

Audit binding:

- Live Plugin API identity: file `csnpEEJfmqFWB0vNUoTkWA`, current top-level
  page `0:1` (`Cover`) and frame `8:2`, verified on 2026-08-21 (Asia/Seoul).
- Code baseline inspected: `main@72afe6db712b145baaba084f64a1ff4fb36d9fd0`
  and PR #824 head `385af92424a6dba338ad9255bc1c920a7dd9f996`.
- Figma's Plugin API does not expose `version` or `lastModified` on a DOCUMENT
  node; a direct version-property query was rejected. Therefore the file key,
  live page/node inventory, check date, and code SHA are the reproducible
  binding. Any later candidate SHA requires fresh visual QA.

This file records the live source of truth for Cloud ERD implementation work.
Use it before the historical PNGs or QA captures in this directory.

## Precedence

1. Concrete nodes present in the current live Figma metadata.
2. Dated Developer Handoff mappings and shared component contracts, only while
   their referenced nodes remain present. When a concrete screen and a
   free-standing variable differ, use the concrete screen unless the handoff
   explicitly maps that property to the variable.
3. Current frontend behavior where Figma explicitly documents it as an intentional extension.
4. Committed QA captures under `docs/ui-ux/qa`.
5. Legacy reference images `01-login-screen.png` through `09-share-export-modal.png`.

The former share/export node `29:143` no longer exists. Do not use it as a live Figma reference.

## Authoritative file

- File key: `csnpEEJfmqFWB0vNUoTkWA`
- Current live frame: `8:2` (`Cover / pg-erd-cloud Design System`)

The supplemental file `OTN0rBGtnVy0P7yq4Iv9Si` contains only its `Page 2`
canvas rather than the product screen inventory, plus conflicting variable
collections. It is a token reference, not the screen authority.

The following screen, handoff, and variable inventory was captured on
2026-08-09 and is historical until each node is reverified in the current
file. The audit recorded 18 pages, including the `Screen Templates` page and
the `Implementation Contracts` node. Its variable collections contained
Primitives (27), Color (51 across Light/Dark), Spacing (17), Radius (4), Sizing
(18), and Typography (16) variables. Counts are dated evidence, not current
API guarantees. The supplemental kit has a smaller conflicting
Primitives/Color/Spacing/Radius inventory with Light/High Contrast modes.

## Historical screen nodes (2026-08-09 audit)

| Screen | Node | Target frame |
| --- | --- | --- |
| Screen inventory | `16:2` | 1440×800 |
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

Supporting contract nodes: screen supplement `45:275`, contract matrix
`130:229`, and the Implementation Contracts audit frame `127:2`.

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
- The public share URL uses `/share/{id}` and renders successful public API snapshots as a read-only ERD. The backend `/api/share/{id}` route remains the data endpoint, and product copy must disclose bearer access, server-controlled expiry, owner API revocation, and the current absence of a UI revoke button.
- Auth loading and authentication-required states reuse the AuthGate card tokens because the live file defines only the idle login state and the repository does not yet provide an OIDC login redirect UI.

## Known Figma defects not to reproduce

- Auth description text is too short for its copy and overlaps the Email label; implementation must allow wrapping and auto height.
- Narrow ModalShell footer examples clip actions; implementation must keep every action visible.
- The ShareExport frame is taller than its 640px showcase frame; implementation must be scroll-safe.
- The general `layout/sidebar-width` variable is 360px, while the concrete ERDEditor screen is explicitly 300/850/290. The screen-scoped implementation follows the concrete screen geometry and retains the general variable in the token inventory.
- The ShareExport frame is 720px wide, while the Developer Handoff explicitly requires modal widths to map to `modal/*`; the implementation therefore uses `modal/export-width` at 500px.
- Dark-mode `color/text/inverse` resolves to dark text over the blue primary action and does not meet the normal-text contrast requirement. The implementation uses white action text as an audited accessibility override.
- The supplied success text/surface pair is below 4.5:1 in light mode and substantially lower in dark mode. The implementation uses darker light-theme and lighter dark-theme success text as audited accessibility overrides.
- The supplied default/subtle borders and React Flow edge defaults fall below the 3:1 non-text contrast requirement when they are the only visible boundary for controls, handles, or relationship edges. The implementation retains the Figma border tokens for structural dividers and uses a dedicated higher-contrast `color/border/control` semantic override for interactive boundaries and relationship lines in both themes.
