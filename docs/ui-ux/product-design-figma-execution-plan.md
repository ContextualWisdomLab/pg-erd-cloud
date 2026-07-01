# Product Design and Figma Execution Plan

This plan turns the current `pg-erd-cloud` MVP into a repeatable Product Design
and Figma workflow. It is grounded in the current product surface, not a generic
design exercise.

## Current Product Evidence

- Product: PostgreSQL and Snowflake schema reverse engineering, ERD rendering,
  snapshot export, reversing-spec generation, and share links.
- Frontend: React 19, Vite, and React Flow under `frontend/src`.
- Existing UI reference source: `docs/ui-ux/README.md` and the nine PNG screens
  in `docs/ui-ux`.
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
- Optional local coded prototype when a selected visual direction needs richer
  interaction.

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

1. Confirm whether to create a new Figma file or use an existing Figma design
   file.
2. Run the Product Design audit against the current screenshots and source UI.
3. If a Figma target is available, import/capture the current references and
   create the page structure above.
4. Build the first clickable prototype around the connection-to-share workflow.
5. Use the prototype review to choose the first implementation PR.

## Open Inputs

- Figma target: existing design file URL/file key or plan key for new-file
  creation.
- Preferred prototype fidelity: static clickable prototype or richer local coded
  prototype.
- First implementation priority: audit fixes, ERD editor, share/export, or
  onboarding/dashboard.
