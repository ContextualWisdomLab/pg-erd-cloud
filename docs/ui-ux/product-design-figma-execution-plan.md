# Product Design and Figma Execution Plan

This plan turns the current `pg-erd-cloud` product surface into a repeatable Product Design
and Figma workflow. It is grounded in the current product surface, not a generic
design exercise.

## Current Product Evidence

- Product: PostgreSQL and Snowflake schema reverse engineering, ERD rendering,
  snapshot export, reversing-spec generation, and share links.
- Frontend: React 19, Vite, and React Flow under `frontend/src`.
- Existing UI reference source: `docs/ui-ux/README.md` and the nine PNG screens
  in `docs/ui-ux`, now placed on the Figma `01 Current References` page.
- Core flow source: `docs/ui-ux/core-user-flow.mmd`.
- Product Design Kit Figma file:
  <https://www.figma.com/design/OTN0rBGtnVy0P7yq4Iv9Si>.
- PR #415 commercial readiness evidence section:
  <https://www.figma.com/design/OTN0rBGtnVy0P7yq4Iv9Si?node-id=63-2>.
- Generated FigJam flow board:
  <https://www.figma.com/board/kHs1cKzwGzkNIBNaMt0xVq?utm_source=codex&utm_content=edit_in_figjam&oai_id=&request_id=b079e329-893d-4418-8909-b22a816fa588>.
- Generated KRW 2B commercial readiness FigJam board:
  <https://www.figma.com/board/XJXqiPUAYyrV85N5XzQpsB?utm_source=codex&utm_content=edit_in_figjam&oai_id=&request_id=abef7f56-0ca9-4a97-9173-0e6ecb254b71>.
- Current visual direction: quiet work-focused layout, persistent left sidebar,
  light palette, blue primary actions, thin borders, subtle shadows, compact
  tables, and dense ERD editor controls.
- Product font basis in code: `system-ui, -apple-system, Segoe UI, Roboto,
  sans-serif`.

## Design Brief

Design and validate a practical Cloud ERD workspace for database engineers and
technical teammates who need to connect a database, create a schema snapshot,
inspect the ERD, adjust metadata, export DDL or diagrams, and share the result.
The interface should feel like an operational tool: dense, calm, keyboard and
screen-reader aware, and optimized for repeated use rather than marketing.

## Execution Status

Status as of 2026-07-02:

- Figma file structure is in place with pages for intake, current references,
  foundations, components, core flow prototype, and QA/handoff.
- `01 Current References` contains all nine repository screenshots as image-fill
  cards using `FIT` scale mode.
- `02 Foundations` contains local Figma variables for primitives, semantic
  colors, spacing, radius, text styles, modal shadow, and focus ring. The
  variable WEB code syntax uses proposed CSS custom property names because the
  current frontend still hardcodes the corresponding values.
- `03 Components` contains editable component sets for button, input field,
  ERD table node, status pill, toolbar button, and share/export modal.
- `04 Core Flow Prototype` contains four connected desktop frames:
  dashboard, connection setup, ERD editor, and share/export. The main CTAs use
  Figma `ON_CLICK -> NAVIGATE` prototype reactions.

Key Figma nodes:

- Foundations summary:
  <https://www.figma.com/design/OTN0rBGtnVy0P7yq4Iv9Si?node-id=17-2>
- Button component set:
  <https://www.figma.com/design/OTN0rBGtnVy0P7yq4Iv9Si?node-id=18-17>
- Input field component set:
  <https://www.figma.com/design/OTN0rBGtnVy0P7yq4Iv9Si?node-id=20-20>
- ERD table node component set:
  <https://www.figma.com/design/OTN0rBGtnVy0P7yq4Iv9Si?node-id=25-78>
- Status pill component set:
  <https://www.figma.com/design/OTN0rBGtnVy0P7yq4Iv9Si?node-id=27-23>
- Toolbar button component set:
  <https://www.figma.com/design/OTN0rBGtnVy0P7yq4Iv9Si?node-id=28-33>
- Share/export modal component set:
  <https://www.figma.com/design/OTN0rBGtnVy0P7yq4Iv9Si?node-id=29-143>
- Core flow prototype dashboard:
  <https://www.figma.com/design/OTN0rBGtnVy0P7yq4Iv9Si?node-id=32-2>
- PR #415 commercial readiness evidence:
  <https://www.figma.com/design/OTN0rBGtnVy0P7yq4Iv9Si?node-id=63-2>

Visual checks completed:

- Foundation summary rendered without clipped text.
- Button, input, table node, status pill, toolbar button, and share/export modal
  component sets were screenshot-checked for overlap and text clipping.
- The ERD editor and share/export prototype frames were screenshot-checked after
  composition.
- The PR #415 commercial readiness evidence board was screenshot-checked and
  stored as `docs/ui-ux/qa/2026-07-02-commercial-readiness-evidence-board.png`.

## Work Packages

### 1. Product Design UX Audit

Scope:

- Login/auth gate.
- Dashboard and recent-project/recent-diagram overview.
- Project list and diagram list.
- ERD editor canvas, toolbar, minimap, table nodes, and empty/busy states.
- Add/edit table, relationship, business group, cardinality, share/export
  modals.

Audit checks:

- Whether the primary workflow is obvious: create project, add connection,
  create snapshot, open ERD, share or export.
- Whether disabled states explain what is required next.
- Whether the editor uses canvas space efficiently on desktop and narrower
  screens.
- Whether toolbar labels, icon-only controls, focus states, live regions, and
  dialog focus traps are sufficient.
- Whether table nodes remain legible with many columns, comments, examples,
  indexes, PK/FK badges, and business groups.
- Whether share/export choices map cleanly to current API capabilities.

Deliverable:

- `docs/ui-ux/product-design-audit.md` with findings ordered by severity, each
  tied to the relevant screen, source component, and proposed fix.

### 2. Figma File and Design System Setup

Required input:

- Existing Figma design file URL or file key, or a Figma plan key so a new file
  can be created.

Proposed Figma pages:

- `00 Intake`: product brief, source links, open decisions.
- `01 Current References`: the nine existing `docs/ui-ux` screenshots and any
  captured running-app screens.
- `02 Foundations`: color, typography, radius, spacing, shadow, focus, and
  status tokens.
- `03 Components`: sidebar, nav item, button, input, select, metric card, data
  table, status pill, ERD table node, toolbar button, modal shell, share/export
  controls.
- `04 Core Flow Prototype`: connected screens for connection-to-share workflow.
- `05 QA and Handoff`: visual diffs, acceptance checklist, implementation notes.

Figma tool use:

- Do not use Figma Code Connect for this project track.
- Use `get_libraries` and `search_design_system` before recreating components,
  variables, or styles.
- Use `generate_figma_design` to capture the running web app into the target
  Figma file when a local or deployed URL is available.
- Use `use_figma` to build editable screens from components, tokens, and
  auto-layout frames, using the app font family confirmed from CSS.
- Validate with Figma screenshots after each major section and verify no text is
  clipped or overlapping.

Deliverable:

- Editable Figma file containing the source references, componentized screens,
  and a clickable prototype.
- Initial Figma file created with pages for intake, current references,
  foundations, components, core prototype flow, and QA/handoff.
- `01 Current References` populated with all nine repository screenshots as
  editable image-fill cards using `FIT` scale mode.
- Local variables and component sets now exist in the Figma file. The next code
  step is to mirror the token names into CSS custom properties before broader
  visual implementation.

### 3. Core Prototype Flow

Prototype path:

1. Auth gate or signed-in workspace entry.
2. Dashboard with recent projects and diagrams.
3. Project creation or project selection.
4. Connection creation with DSN validation guidance.
5. Snapshot creation and busy/empty states.
6. ERD editor with search, auto-layout, table add/edit, relationship edit,
   business grouping, cardinality recommendations, and exports.
7. Share/export modal with link creation, copy feedback, and DDL export.

Interaction level:

- First pass: clickable screen prototype with modal open/close states and
  realistic data.
- Second pass: local frontend prototype or code PR only after the first pass is
  reviewed.

Deliverables:

- Figma prototype links for the desktop flow.
- FigJam user-flow board for the core connection-to-share journey.
- Optional local coded prototype when a selected visual direction needs richer
  interaction.
- First Figma pass complete: dashboard -> connection setup -> ERD editor ->
  share/export, with clickable navigation on the main CTAs.

### 4. Design QA Before Implementation

Compare:

- Existing screenshots in `docs/ui-ux`.
- Running local app screenshots at desktop width and a narrower viewport.
- Figma componentized output.

QA checks:

- Sidebar width, spacing, active states, and focus visibility.
- Dashboard card density and table scannability.
- Modal padding, title hierarchy, close button affordance, and form-first layout.
- ERD canvas framing, toolbar density, minimap placement, and empty/busy states.
- Table node readability for long names, comments, examples, badges, and indexes.
- Export/share copy, loading, error, and disabled states.
- Keyboard flow and dialog focus return.

Deliverable:

- `docs/ui-ux/design-qa-checklist.md` as the standing pre-implementation QA
  gate.
- `docs/ui-ux/design-qa-report.md` with screenshots or Figma node links,
  mismatches, decisions, and implementation-ready fixes.

### 5. Implementation PR Path

Only start code changes after the audit and Figma direction identify a specific
screen or interaction to update.

Candidate frontend targets:

- `frontend/src/App.tsx` for workspace flow, editor toolbar, empty states, and
  share/export entry points.
- `frontend/src/styles.css` for design tokens, density, focus states, responsive
  layout, and visual polish.
- `frontend/src/erd/TableNode.tsx` for ERD node readability, badges, indexes,
  comments, and example values.
- `frontend/src/components/modals/*` for modal structure, copy, disabled states,
  and accessibility refinements.

Verification:

- `cd frontend && npm run typecheck`
- `cd frontend && npm test`
- `cd frontend && npm run build`
- Browser screenshot check for dashboard, editor, and share/export modal.

Deliverable:

- A focused PR with the design decision, Figma/screenshot evidence, and test
  output in the PR body.

## Immediate Next Actions

1. Review the Figma component sets and core flow prototype with product and
   engineering stakeholders.
2. Choose the first implementation PR scope. The recommended first scope remains
   share/export because it has a focused component and clear audit finding.
3. Capture the running local app into Figma when a browser-verifiable URL is
   available, then compare it against the repository screenshots and current
   Figma components.
4. Mirror the Figma token names into CSS custom properties before broad visual
   implementation.
5. Use the implementation QA checklist before merging any UI code PR.

## Open Inputs

- First implementation priority: audit fixes, ERD editor, share/export, or
  onboarding/dashboard.
- Whether narrow-width work should stay review/share-only or include full mobile
  editing.
