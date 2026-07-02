# Design QA Checklist

Use this checklist before implementing or merging UI changes derived from the
Product Design and Figma work. It is not a final QA report by itself; a passing
QA decision requires side-by-side evidence from both a source visual target and a
rendered implementation.

## Required Evidence

- Source visual target:
  - Figma design node, FigJam flow board, screenshot, mockup, or `docs/ui-ux`
    reference PNG.
  - Record the URL or file path.
- Rendered implementation:
  - Local or deployed app screenshot of the same state.
  - Record the URL, viewport, browser, and screenshot file path.
- Same-state match:
  - Same route or workspace view.
  - Same selected project/diagram state.
  - Same modal open/closed state.
  - Same data density where possible.
  - Same viewport class: desktop editor, narrow review layout, or modal-focused
    capture.

## Current Figma Baseline

Use these source nodes for the first implementation comparison pass:

- Component foundations:
  <https://www.figma.com/design/OTN0rBGtnVy0P7yq4Iv9Si?node-id=17-2>
- ERD table node density variants:
  <https://www.figma.com/design/OTN0rBGtnVy0P7yq4Iv9Si?node-id=25-78>
- Editor toolbar button variants:
  <https://www.figma.com/design/OTN0rBGtnVy0P7yq4Iv9Si?node-id=28-33>
- Share/export modal states:
  <https://www.figma.com/design/OTN0rBGtnVy0P7yq4Iv9Si?node-id=29-143>
- Core flow prototype dashboard:
  <https://www.figma.com/design/OTN0rBGtnVy0P7yq4Iv9Si?node-id=32-2>

The Figma component and prototype screenshots were checked for clipped text and
overlap during the design pass. A code implementation still requires a separate
browser screenshot comparison before merge.

## Required Screens

Run the QA pass on these screens before broad UI implementation:

1. Auth gate or signed-in entry.
2. Dashboard with recent projects and diagrams.
3. Project list with empty and populated states.
4. Diagram list with empty, running, succeeded, and failed statuses when
   available.
5. First-run setup path for project, connection, DSN, schema filter, and
   snapshot creation.
6. ERD editor with at least four tables, relationships, minimap, toolbar, and
   search.
7. ERD editor empty state and snapshot-running state.
8. Table node stress state with long names, comments, examples, PK/FK badges,
   NOT NULL badges, indexes, and business group badge.
9. Add/edit table modal.
10. Relationship settings modal.
11. Business group modal.
12. Cardinality recommendation modal.
13. Share/export modal with no project, loading, success, copy-feedback, error,
    and no-DDL states.
14. Narrow viewport review/share state.

## Fidelity Surfaces

### Fonts and Typography

- Product font family follows the source target and implementation CSS.
- Heading, body, table, caption, badge, and monospace export text sizes are
  visually consistent.
- Line heights do not crop Korean or English text.
- Long schema, table, column, index, and URL values wrap or truncate
  intentionally.
- Button and toolbar labels fit their controls at all required viewport widths.

### Spacing and Layout Rhythm

- Sidebar width, padding, and section gaps match the design target.
- Dashboard cards and tables align to the same grid rhythm.
- Toolbar groups do not overlap the canvas, minimap, empty state, or React Flow
  controls.
- Modals preserve header, section, form, and action spacing at desktop and narrow
  widths.
- Table node density remains scannable with high metadata volume.

### Colors and Visual Tokens

- Primary blue, active states, focus ring, borders, neutral text, status colors,
  and modal shadows map to named Figma variables or CSS custom properties.
- Disabled states remain legible and distinguishable from active controls.
- Status pills communicate succeeded, failed, running, and not-found states
  without relying on color alone.
- Business group colors remain distinguishable against table-node backgrounds.

### Image and Asset Fidelity

- Use real source screenshots, Figma captures, product icons, or an approved icon
  library.
- Do not replace product-relevant icons or screenshots with placeholder boxes,
  CSS drawings, text glyphs, or handcrafted approximations.
- ERD canvas captures must show real table-node content, relationship lines, and
  controls rather than blank canvas placeholders.

### Copy and Content

- Korean and English labels use one consistent product voice per surface.
- Toolbar, modal, and disabled-state copy explains the next action.
- Share/export copy distinguishes project share links from DDL text and diagram
  file exports.
- DSN and schema-filter hints are explicit about PostgreSQL and Snowflake.
- Error states say what failed and what the user can try next.

## Accessibility Checks

- Keyboard can reach every visible control in a logical order.
- Skip link lands on the main workspace.
- Focus ring is visible against all backgrounds.
- Dialogs trap focus, close on Escape, and return focus to the opener.
- Destructive actions are not adjacent to primary actions without enough visual
  separation.
- `aria-live` regions announce snapshot, copy, loading, and search-result
  changes without excessive noise.
- Icon-only toolbar actions have accessible names and visible tooltips.
- Tables and table-like rows expose useful structure to assistive tech.

## QA Report Format

Save each implementation QA pass as `docs/ui-ux/design-qa-report.md` or as a
dated file under `docs/ui-ux/qa/`.

Required fields:

- Source visual truth path or Figma node URL.
- Implementation URL and screenshot path.
- Viewport and state.
- Full-view comparison evidence.
- Focused-region comparison evidence for toolbar, table node, and modal details,
  or a reason focused regions were not needed.
- Findings ordered by severity.
- Fix checklist.
- Final result: `passed` or `blocked`.

Use `passed` only when no actionable P0, P1, or P2 findings remain. P3 polish
can remain as follow-up. Use `blocked` when any actionable P0, P1, or P2 finding
remains.

## First QA Target

Start with the share/export modal because it is the recommended first
implementation surface from `product-design-audit.md` and has a clear existing
reference in `09-share-export-modal.png`.

First source target:
<https://www.figma.com/design/OTN0rBGtnVy0P7yq4Iv9Si?node-id=29-143>
