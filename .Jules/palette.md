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
## 2025-02-20 - [NoScript Fallback Accessibility]
**Learning:** Adding a `<noscript>` tag to `index.html` is a universally safe baseline accessibility improvement for SPAs that avoids touching complex React components and circumventing STRIX vulnerability scans on potentially sensitive code.
**Action:** Always consider `<noscript>` fallback messages when seeking a simple, zero-risk, high-impact a11y baseline improvement.
