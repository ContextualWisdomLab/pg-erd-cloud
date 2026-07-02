# Visual Regression Baseline Policy

This policy defines when `pg-erd-cloud` visual snapshots can change. Visual
baselines are release gates, not cosmetic artifacts. A changed baseline is
acceptable only when the product change is intentional, reviewed, and backed by
browser evidence.

## Covered Baselines

The current CI gate runs `npm run test:visual` in Chromium demo mode and checks
these snapshots:

| Surface | Browser | Viewport | Snapshot |
|---|---:|---:|---|
| Desktop ERD editor | Chromium | `1280x720` | `frontend/e2e/__screenshots__/chromium/visual-regression.spec/demo-editor.png` |
| Mobile review/editor entry | Chromium | `390x844` | `frontend/e2e/__screenshots__/chromium/visual-regression.spec/demo-editor-mobile.png` |

The mobile baseline is scoped to review and navigation confidence. Full mobile
ERD editing is not a release promise until Product Design defines that workflow.

## Approval Requirements

Every PR that updates a visual baseline must include:

- The intentional product reason for the visual change.
- Source visual evidence: a Figma node, FigJam board, approved mockup, or
  `docs/ui-ux` reference screenshot.
- Rendered browser evidence from the same state, including route, viewport,
  browser, and screenshot path.
- A short note confirming that no text is clipped, no controls overlap, the
  canvas shows diagram content or the intended empty state, and
  toolbar/search/share controls remain visible.
- Approval from the product/design owner or release owner before merge.

## Update Procedure

1. Run `npm run test:visual` before accepting the new baseline and inspect the
   generated diff or missing-snapshot failure.
2. Confirm the diff matches an intentional product/design change.
3. Regenerate snapshots with `npm run test:visual -- --update-snapshots`.
4. Re-run `npm run test:visual`.
5. Re-run the adjacent browser gates: `npm run test:e2e` and
   `npm run test:a11y`.
6. Record the evidence in the PR body or a dated QA report under
   `docs/ui-ux/qa/`.

## No-Go Conditions

Do not approve a visual baseline update when any of these are present:

- Blank or mostly blank canvas without the intended empty-state panel.
- Missing primary navigation, editor toolbar, search, or share/export control.
- Korean or English labels clipped by buttons, panels, table nodes, or modals.
- Controls overlapping each other, the canvas, minimap, or modal content.
- Mobile viewport hiding the review/share path needed by non-editing users.
- Snapshot change caused only by nondeterminism, loading state drift, or test
  data instability.
