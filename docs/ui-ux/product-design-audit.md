# Product Design UX Audit

Date: 2026-07-02

Audit scope: `pg-erd-cloud` workspace from project entry through ERD inspection,
editing, share, and export.

Evidence used in this pass:

- Repository screenshots in `docs/ui-ux/01-login-screen.png` through
  `docs/ui-ux/09-share-export-modal.png`.
- Current frontend source in `frontend/src/App.tsx`,
  `frontend/src/styles.css`, `frontend/src/erd/TableNode.tsx`, and
  `frontend/src/components/modals/*`.

Evidence limits:

- This is a local repository audit, not a completed Figma-board audit. A Figma
  file URL/file key or plan key is still needed before screenshots and notes can
  be placed in Figma.
- Screenshots show the intended product direction, while source review shows the
  current implementation. Live keyboard traversal, screen-reader output, backend
  latency, and real database-scale behavior still need browser verification.

## Flow Steps

1. Login/auth gate
   - Health: usable direction, needs live validation.
   - Evidence: `01-login-screen.png`, auth-gate code in `frontend/src/App.tsx`.

2. Dashboard overview
   - Health: strong information architecture direction.
   - Evidence: `02-dashboard-screen.png`; current dashboard, metrics, project
     cards, and recent diagram table in `frontend/src/App.tsx`.

3. Project list
   - Health: clear enough for MVP, needs density and empty-state polish.
   - Evidence: `03-project-list-screen.png`; project list rows and inline create
     path in `frontend/src/App.tsx`.

4. Diagram list
   - Health: clear enough for snapshot browsing, needs state clarity.
   - Evidence: `04-diagram-list-screen.png`; `DiagramTable` and status pills in
     `frontend/src/App.tsx` and `frontend/src/styles.css`.

5. New diagram / connection setup
   - Health: functionally present, but the workflow is split between reference
     modal direction and current editor-sidebar implementation.
   - Evidence: `05-new-diagram-modal.png`; project, connection, DSN, schema
     filter, and snapshot controls in `frontend/src/App.tsx`.

6. ERD editor
   - Health: strongest surface in the product, with dense controls and useful
     accessibility hooks; needs clearer visual grouping.
   - Evidence: `06-erd-editor-main.png`; toolbar, React Flow canvas, empty/busy
     state, minimap, controls, and table nodes in `frontend/src/App.tsx`,
     `frontend/src/styles.css`, and `frontend/src/erd/TableNode.tsx`.

7. Add/edit entity
   - Health: covers core editing, but modal styling is less consistent than the
     newer modal shell.
   - Evidence: `07-add-entity-modal.png`; `EditTableModal.tsx`,
     `AddTableModal.tsx`, and modal CSS.

8. Relationship settings
   - Health: usable for MVP relationship labeling, needs clearer destructive and
     save/cancel hierarchy.
   - Evidence: `08-relationship-settings-modal.png`; `EditEdgeModal.tsx`.

9. Share/export
   - Health: strategically important and already implemented as a combined
     modal; needs clearer separation of sharing, DDL, and image/diagram exports.
   - Evidence: `09-share-export-modal.png`; `ExportModal.tsx` and export toolbar
     entry points in `frontend/src/App.tsx`.

## Findings

### P1. Setup workflow is split between the product concept and current editor sidebar

Evidence:

- The reference set includes a new-diagram modal, while the current implementation
  exposes project selection, project creation, connection creation, DSN entry,
  schema filtering, and snapshot creation inside the editor sidebar.
- In `frontend/src/App.tsx`, the editor-only sidebar controls run from project
  selection through `Reverse engineer -> snapshot`.

Impact:

- First-time users can complete the task, but the path is operationally dense
  before they understand what the ERD editor is for.
- The dashboard and list screens sell a workspace model, while the editor sidebar
  carries setup, configuration, status, and navigation at once.

Recommendation:

- Keep the sidebar for selected-project context and advanced controls.
- Move first-run project/connection/snapshot creation into a guided "New
  diagram" or "Create snapshot" modal/drawer that matches `05-new-diagram-modal`.
- In Figma, prototype both states: first-run setup and returning-user editor.

### P1. ERD toolbar has many compact controls with mixed symbolic labels

Evidence:

- Toolbar labels include `↔`, `↶`, `+`, `◇`, `#`, `SQL`, `↗`, `IMG`, `UML`, and
  `{}` in `frontend/src/App.tsx`.
- CSS gives each toolbar button a compact 44 x 40 minimum target.

Impact:

- The toolbar is dense, which is appropriate for an editor, but the visual
  language mixes symbols, abbreviations, and text labels.
- Screen-reader labels are present, but sighted users must rely on hover titles
  for several actions.

Recommendation:

- Define a Figma toolbar component with grouped regions: layout, create/edit,
  analysis, share/export.
- Replace symbolic labels with consistent icon buttons plus tooltips, keeping
  visible text only where the term itself is the format (`SQL`, `UML`).
- Add the grouped toolbar to the first implementation PR only after the Figma
  direction is approved, because tests currently assert several visible labels.

### P1. Share/export is strategically central but visually overloaded

Evidence:

- The reference screen shows share and export as two side-by-side concepts.
- `ExportModal.tsx` combines project share-link generation and DDL copy in a
  single modal. Separate toolbar actions also trigger SVG, PlantUML, and Mermaid
  exports directly from the toolbar.

Impact:

- Users may not understand which exports are project-level share links, which
  are current-canvas text exports, and which are immediate file downloads.
- This matters because share links expose API-backed project resources while DDL,
  SVG, PlantUML, and Mermaid are different artifact types.

Recommendation:

- In Figma, redesign share/export as a two-column or tabbed modal with clear
  sections: Share link, SQL DDL, Diagram image, Diagram text formats.
- Add explicit disabled reasons and copy feedback to every export type.
- In code, route all export-related actions through one modal once the visual
  model is approved.

### P2. Modal system is partly consolidated and partly bespoke

Evidence:

- `ExportModal.tsx` uses `modalContent`, `modalHeader`, and structured sections.
- `EditTableModal.tsx` still uses a `modal` class with inline width, max-height,
  overflow, row, spacing, and button styles.
- `useDialogAccessibility.ts` provides useful focus trapping, Escape handling,
  and focus return behavior.

Impact:

- Accessibility behavior is on the right track, but visual consistency and
  maintainability are uneven across modals.
- Inline styles make it harder to map modals cleanly into Figma components and
  design tokens.

Recommendation:

- Create a Figma `Modal/Shell` component and variant rules for default,
  destructive, form-heavy, and split-section modals.
- Refactor modal CSS toward shared classes before broad visual polish.
- Keep `useDialogAccessibility` as a strength and verify it with keyboard tests.

### P2. ERD table nodes optimize density, but large schemas need progressive disclosure

Evidence:

- `TableNode.tsx` renders title, comment, group badge, PK/FK badges, column
  comments, example values, data types, NOT NULL badges, and indexes.
- The component renders up to 25 columns and four indexes before showing a
  "more" indicator.

Impact:

- Dense schema context is valuable, but nodes can become tall and visually noisy
  as comments, examples, and indexes accumulate.
- Users auditing relationships may need a quick "keys only" or "compact" mode
  before reading all metadata.

Recommendation:

- In Figma, define three table-node density variants: compact, standard, and
  detail.
- Keep comments/examples/indexes available, but make detail expansion explicit.
- Validate with a stress case containing long schema/table names, 25+ columns,
  multiple indexes, and business group badges.

### P2. Responsive behavior exists, but mobile/narrow-width product intent is unclear

Evidence:

- CSS includes breakpoints at `1180px` and `767px`.
- At small widths, the sidebar becomes a top region, nav becomes four columns,
  data tables scroll horizontally, and the canvas toolbar stretches across the
  top of the canvas.

Impact:

- The product is primarily a desktop ERD editor. Narrow layouts are present, but
  the expected mobile task is not defined.
- Without a target task, mobile work may become a compromised version of a
  desktop editor rather than a useful review/share experience.

Recommendation:

- Define narrow-width scope as "review and share" unless full mobile editing is
  explicitly required.
- In Figma, create a narrow review-mode screen that prioritizes project summary,
  diagram preview, search, and share/export over full canvas editing.

### P3. Design tokens are implicit in CSS rather than explicit in a system

Evidence:

- CSS repeats key colors such as `#034ea2`, `#e5e7eb`, `#64748b`, `#0f172a`,
  `#f8fafc`, and `#fff`.
- Radius, spacing, focus ring, table density, and modal shadow values are defined
  directly in component classes.

Impact:

- The visual direction is coherent, but Figma cannot stay linked to code without
  named tokens.
- Future PRs may drift if each screen hardcodes spacing and colors independently.

Recommendation:

- Define Figma variables for color, spacing, radius, shadow, typography, focus,
  and status.
- Mirror the naming in CSS custom properties before the first broad visual PR.

### P3. Current screenshot references are useful but not yet an editable design system

Evidence:

- `docs/ui-ux` contains nine raster reference screens and a concise direction
  note.
- There is no Figma file link, component inventory, token inventory, or design QA
  baseline in the repository yet.

Impact:

- The team has product direction, but not a durable editable source for design
  review, prototype links, or implementation handoff.

Recommendation:

- Use the execution plan in
  `docs/ui-ux/product-design-figma-execution-plan.md` to create a Figma file
  with pages for references, foundations, components, prototype, and QA.
- Add the Figma file link back to `docs/ui-ux/README.md` after creation.

## Strengths To Preserve

- The existing direction is appropriately work-focused: no marketing hero,
  restrained color, compact tables, and a persistent workspace frame.
- Accessibility basics are already considered: skip link, focus-visible styles,
  dialog focus trap, Escape close behavior, focus return, `aria-live`, and
  `role="alert"` appear in the implementation.
- ERD-specific capabilities are real product differentiators: React Flow canvas,
  table search/highlight, auto-layout, business grouping, cardinality
  recommendations, generated examples, and multiple export formats.
- The reference screenshots already cover the major workspace states needed for
  a first Figma design system pass.

## Recommended First PR After Figma Review

Start with the share/export surface because it is central to collaboration,
already has a focused component (`ExportModal.tsx`), and has clear reference
material in `09-share-export-modal.png`.

Suggested PR scope:

- Redesign the modal into clearer sections for share link, DDL, and diagram
  exports.
- Keep existing API behavior unchanged.
- Add or update tests for disabled states, copy feedback, and error rendering.
- Verify with `cd frontend && npm run typecheck`, `cd frontend && npm test`, and
  `cd frontend && npm run build`.
