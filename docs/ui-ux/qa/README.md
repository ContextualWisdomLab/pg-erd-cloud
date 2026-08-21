# UI/UX QA Evidence

This folder stores visual QA captures used to compare Figma source designs against rendered frontend implementation states.

## 2026-08-09 Live Alignment Pass

The current contract is recorded in `../figma-contract.md`, and the current QA
result is recorded in the repository-root `design-qa.md`. No new implementation
screenshots are claimed for this pass: the approved cloud browser could not
reach the isolated local Vite server, so same-viewport visual comparison remains
blocked. The historical captures below are not current pass evidence.

- `2026-08-09-live-figma-alignment.html`: code-contract visualization and verification summary; it is not a rendered implementation screenshot.

## 2026-07-02 Share Export Modal

Historical evidence only. The referenced node `29:143` has been deleted from
the live Figma files. Use `../figma-contract.md` and live ShareExport node
`130:232` for current implementation decisions.

- `2026-07-02-figma-share-export-modal.png`: Figma source node `29:143`.
- `2026-07-02-implementation-share-export-modal.png`: rendered default state at `1440x900`.
- `2026-07-02-implementation-share-export-success-modal.png`: rendered copied-link success state at `1440x900`.
- `2026-07-02-implementation-share-export-mobile.png`: rendered mobile state at `390x844 @ 2x`.
- `2026-07-02-share-export-comparison.png`: combined comparison evidence.
