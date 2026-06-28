## 2025-02-24 - Accessibility and Disabled States for Forms
**Learning:** In forms without `<form>` elements (where input and buttons are siblings), adding explicit `<label>` tags is difficult without changing the design layout. In such cases, explicitly adding an `aria-label` attribute directly to the inputs (`<input>`) is essential so screen readers can distinguish between inputs (like `dsn` and `conn-name` inputs without standard `<label>` groupings). Disabled buttons should not rely on `title` because many browsers do not expose disabled-control tooltips.
**Action:** When working on standalone functional forms with multiple inputs, ensure secondary inputs that lack a traditional wrapping label tag include an `aria-label`. Pair disabled buttons with visible helper text and `aria-describedby` so the disabled reason remains available to mouse, keyboard, and screen-reader users.
## 2024-05-24 - [Replaced blocking alert with inline copy feedback]
**Learning:** Native browser alerts for micro-interactions (like copying text) are disruptive to the user flow. Replacing them with temporary inline button text updates (`aria-live="polite"`) significantly improves both the experience and accessibility for screen readers.
**Action:** Always prefer non-blocking inline feedback or toast notifications over `alert()` or `confirm()` dialogs for non-destructive actions.
## 2026-06-20 - Adding async operation loading states to critical UX paths
**Learning:** This app requires manual yielding to the browser during compute-heavy or async events (like `onAutoLayout` with `requestAnimationFrame`). For typical network requests, standard state flags for disabling/progressing buttons with `aria-busy` provides sufficient UX feedback without freezing the UI.
**Action:** When adding new network operations in this stack, consistently use dedicated loading state flags and apply `aria-busy` attributes paired with disabled logic to inform the user.
## 2026-06-20 - [Canvas Empty States]
**Learning:** In canvas-based applications (like React Flow ERDs), an empty canvas can look like a broken state or a loading delay if no guidance is provided. When no nodes are present, users need immediate visual feedback explaining *why* it's empty (e.g., waiting for reverse engineering) or *what* to do next (e.g., "Create a snapshot" or "Add a table").
**Action:** Always implement an empty state for infinite canvas components that clearly distinguishes between 'loading/generating' and 'ready for interaction' to reduce user confusion.
## 2026-06-21 - Disabled button visual feedback
**Learning:** By default, buttons missing `:disabled` pseudo-class styling lack visual cues and keep a pointer cursor, leading to user confusion about interactivity.
**Action:** Always ensure disabled buttons have reduced opacity, a not-allowed cursor, and optionally a different background/text color to clearly distinguish them from active buttons.
## 2026-06-21 - Custom Modals and ARIA Context
**Learning:** Custom generic `<div>` components mimicking native elements (like modals) frequently lack basic ARIA boundaries (`role="dialog"`, `aria-modal="true"`) and contextual naming, leading to screen reader confusion. Additionally, using `aria-label` on non-interactive generic elements (like an outer `div` wrapping list items) without a corresponding role (e.g. `role="group"`) is commonly ignored by assistive tech.
**Action:** Always ensure custom modals implement the `dialog` role with an explicit `aria-modal="true"` and an `aria-labelledby` referencing their heading. For non-interactive elements containing labeled groups, explicitly assign `role="group"` or a relevant semantic role when applying an `aria-label`.
## 2025-02-23 - Add Confirmation and Accessibility to Destructive Actions
**Learning:** In the ERD canvas, destructive actions like deleting relations or business groups were missing user confirmation, increasing the chance of accidental data loss. Furthermore, mapped lists of interactive elements like "Business Group" rendering generic "삭제" (delete) buttons lacked `aria-label` context, creating ambiguous screen reader experiences.
**Action:** Next time, always wrap destructive handlers with `window.confirm` dialogues and ensure mapped delete buttons receive an `aria-label` providing full context (e.g., `aria-label={`${itemName} 삭제`}`).
## 2024-05-25 - [Button Semantics and `type="button"`]
**Learning:** In a typical React SPA with numerous `<button>` elements, if the `type` attribute is omitted, the browser defaults to `type="submit"`. Even if these buttons are not currently inside `<form>` elements, relying on the default is a potential UX/a11y bug because a future refactoring that adds a `<form>` wrap can lead to unintended form submissions (and page reloads) when action buttons (like "Cancel" or "Close") are clicked.
**Action:** Always explicitly define `type="button"` for JavaScript-driven action buttons that are not intended to submit a form.

## 2026-06-21 - Form Input Keyboard Navigation
**Learning:** Standalone inputs without wrapping `<form>` elements inherently lack keyboard submission support, forcing users to switch from keyboard to mouse just to complete simple forms. Furthermore, modal dialogues holding inputs trap keyboard users unless explicit cancelation escapes are implemented.
**Action:** When implementing inputs outside of standard `<form>` contexts or within custom modals, explicitly add `onKeyDown` handlers to support `Enter` for submission and `Escape` for cancelation.

## 2024-06-23 - [Safe Scope UX Tooltips]
**Learning:** Adding helpful `title` tooltips to text indicating truncation (e.g., "... N more") significantly improves usability for screen readers and confused users without changing visual layouts. More importantly, when working in a repository with aggressive penetration testing (like STRIX), UX changes must avoid touching components that handle sensitive inputs (like `App.tsx` dealing with DSNs). If an agent modifies a vulnerable file, even just for a UX change, the CI will run the pen-test against that file and block the PR.
**Action:** Always verify the security posture of a file before making non-security changes to it. Prefer touching isolated display components (like `TableNode.tsx`) for UX enhancements rather than high-risk root components.
