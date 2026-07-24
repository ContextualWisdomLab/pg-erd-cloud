## 2026-07-14 - Accessible Abbreviation Badges in ERD Nodes
**Learning:** ERD nodes are dense with domain abbreviations ("PK", "FK", "NN", "NOT NULL") that visually capable DBAs parse instantly but that confuse screen-reader users and beginners. Three refinements emerged in sequence: a bare `title` tooltip only helps mouse users; `aria-label` on the wrapper provides the screen-reader name; and adding `aria-hidden="true"` on the inner visual text stops screen readers from announcing both the abbreviation and its expansion. Forcing focusability with `tabIndex` on non-interactive badges harms keyboard ergonomics.
**Action:** For abbreviation badges, put a descriptive `aria-label` (e.g. "Primary Key") on the wrapper element, keep `title` only as a mouse-hover convenience, hide the raw abbreviation text with `aria-hidden="true"`, and do not add `tabIndex` to non-interactive elements.

## 2026-07-11 - Explicit aria-labels on Row-Scoped and Standalone Inputs
**Learning:** Inputs rendered per table row (e.g. Distinct Count, Group Assignment selects) or as siblings in label-less layouts (e.g. `dsn`, `conn-name`) lose their row/context identity for screen-reader users, who hear only a generic control name when focusing them.
**Action:** Give each such input an explicit `aria-label` that carries the full context (e.g. `${column.column_name} distinct count`, `${node.data.title} group assignment`), even when a visual label sits next to it.

## 2026-07-05 - Announcing Why a Control Is Disabled
**Learning:** Fully disabled native buttons are unfocusable in many browsers, so neither `title` tooltips nor `aria-describedby` reliably convey the disabled reason; the "why" disappears for keyboard and screen-reader users.
**Action:** Pair unavailable actions with visible helper text. When the reason must be announced on focus, use `aria-disabled="true"` plus a click/key guard and `aria-describedby`; reserve native `disabled` for cases where removing the control from the focus order is intentional.

## 2026-06-30 - Text Truncation Accessibility
**Learning:** Elements using `text-overflow: ellipsis` and "... N more" overflow summaries hide table, column, example, and group context from users who cannot hover; a `title` tooltip alone leaves keyboard and touch users without the full value.
**Action:** Treat native `title` as a convenience hover fallback only. Pair truncated text with an accessible name or description carrying the full value, and make the truncated element focusable when the full text is otherwise unreachable.

## 2026-06-30 - SPA Noscript Fallbacks
**Learning:** A JavaScript-only SPA renders a blank screen when scripts are disabled, which is especially confusing for assistive-technology users and locked-down browser environments.
**Action:** Add a localized `<noscript>` fallback near the top of `<body>` for SPA entry pages. Keep the message in the same language as the document `lang` value, or mark different-language text with its own `lang` attribute.

## 2026-06-23 - Keyboard Navigation for Standalone Inputs and Modals
**Learning:** Standalone inputs without a wrapping `<form>` element lack implicit Enter-to-submit behavior, forcing keyboard users onto the mouse, and custom modal dialogs trap keyboard users unless an explicit escape path exists.
**Action:** When implementing inputs outside `<form>` contexts or inside custom modals, add `onKeyDown` handlers supporting `Enter` for submission and `Escape` for cancelation.

## 2026-06-23 - Keep UX Changes Scoped; Fix Security Findings, Never Dodge Them
**Learning:** In this repository, security scanners (STRIX) and strict reviewers analyze every file a PR touches. A "single micro-UX improvement" task that spreads across multiple files fails review for scope creep, and touching a component that handles sensitive inputs (e.g. DSN handling in `App.tsx`) can surface pre-existing vulnerabilities in CI.
**Action:** Keep each micro-UX change isolated to one element and file. If a scanner flags a real vulnerability in a file you touched, fix it or report it explicitly — do not select files to avoid scanner attention, and never treat working around security review as an acceptable goal.

## 2026-06-22 - Add Confirmation and Accessibility to Destructive Actions
**Learning:** Destructive ERD canvas actions (deleting relations or business groups) executed immediately with no confirmation, and mapped lists rendered generic delete buttons without per-item context for screen readers.
**Action:** Wrap destructive handlers in a confirmation step (e.g. `window.confirm`) and give mapped delete buttons a contextual `aria-label` naming the target item (e.g. ``aria-label={`Delete ${itemName}`}``).

## 2026-06-21 - Custom Modals and ARIA Context
**Learning:** Custom `<div>`-based modals frequently lack ARIA boundaries (`role="dialog"`, `aria-modal="true"`) and contextual naming, confusing screen readers. Separately, `aria-label` on a non-interactive generic element (like an outer `div` wrapping list items) is ignored by assistive tech unless the element also has a role.
**Action:** Give custom modals `role="dialog"`, explicit `aria-modal="true"`, and `aria-labelledby` referencing their heading. When applying `aria-label` to a non-interactive container, also assign `role="group"` or another appropriate semantic role.

## 2026-06-21 - Disabled Button Visual Feedback
**Learning:** Buttons without `:disabled` styling keep full opacity and a pointer cursor, so users cannot tell they are inactive.
**Action:** Ensure disabled buttons have reduced opacity, a `not-allowed` cursor, and optionally a distinct background/text color to clearly distinguish them from active buttons.

## 2026-06-20 - Async Operation Loading States
**Learning:** Compute-heavy handlers (like `onAutoLayout`) need manual yielding to the browser (`requestAnimationFrame`), while ordinary network requests only need state flags that disable the trigger and signal progress; `aria-busy` communicates the in-flight state to assistive tech without freezing the UI.
**Action:** For new network operations, consistently add a dedicated loading-state flag, disable the triggering control while pending, and set `aria-busy` on the affected region.

## 2026-06-20 - Canvas Empty States
**Learning:** An empty infinite canvas (React Flow ERD) reads as broken or still loading when nothing explains why it is empty or what to do next (e.g. waiting for reverse engineering vs. "Create a snapshot").
**Action:** Implement explicit empty states for canvas components that distinguish 'loading/generating' from 'ready for interaction' and point to the next action.

## 2026-06-19 - Non-Blocking Inline Copy Feedback
**Learning:** Native browser alerts for micro-interactions (like copying text) interrupt user flow; temporary inline button-text updates announced via `aria-live="polite"` improve both experience and screen-reader accessibility.
**Action:** Prefer non-blocking inline feedback or toast notifications over `alert()`/`confirm()` for non-destructive actions.
