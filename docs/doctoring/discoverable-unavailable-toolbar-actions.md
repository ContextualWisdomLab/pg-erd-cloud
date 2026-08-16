# Discoverable unavailable toolbar actions

## Status

Implemented on pull request #858. This record describes a bounded canvas-toolbar interaction contract. It does not claim whole-product WCAG conformance, complete assistive-technology interoperability, a fully conforming composite `toolbar` widget, or a final shared design-system component.

## Buyer-visible outcome

Temporarily unavailable editor actions remain discoverable to keyboard, screen-reader, and pointer users. Native `disabled` removes a button from sequential focus and commonly suppresses pointer interaction, which can hide the action and its prerequisite. The canvas toolbar therefore keeps these actions as native buttons and exposes `aria-disabled="true"` while the business condition is unmet.

Each unavailable action:

- remains in the sequential Tab order;
- retains its accessible name;
- references a rendered reason through `aria-describedby`;
- exposes the same reason on hover and `:focus-visible`;
- preserves the unavailable visual treatment through the existing design tokens;
- rejects pointer, Enter, and Space activation in the click guard;
- does not open a modal, mutate nodes, invoke inference, confirm deletion, or start export while unavailable.

Auto-layout and undo additionally use the active busy reason while layout is running. `aria-busy` remains on the operation that owns the pending state.

## Standards boundary

The WAI-ARIA Authoring Practices keyboard-interface guidance recognizes two valid conventions: most disabled controls should leave the focus order when their presence is inferable, while actions whose discoverability is important may remain focusable with `aria-disabled="true"`. The APG uses copy, cut, and paste toolbar actions as an example of the latter case. The button pattern further requires `aria-disabled="true"` when a button action is unavailable and `aria-describedby` when a functional description is present.

The tooltip pattern describes hover/focus disclosure with the trigger retaining focus and referencing a `role="tooltip"` element through `aria-describedby`. That pattern remains marked as work in progress and lacks task-force consensus. Accordingly, this repository treats the rendered reason as an accessible description first and a visual tooltip second. Product correctness does not depend on native `title` behavior or on a claim of complete APG tooltip conformance.

These editor actions are stable product capabilities that users cannot infer from a neighboring enabled equivalent. Keeping them discoverable is therefore an explicit product choice. This choice does not imply that every unavailable control in the application should remain focusable.

## Interaction invariants

- A native `button` remains the activation element; no custom button role is introduced.
- The guarded handler is the final authority and checks the same state that sets `aria-disabled` and the reason text.
- Enter and Space reach the native click path and are rejected by the same guard.
- The action must not call a destructive confirmation while unavailable.
- The description identifier is unique within the document.
- Reason text must change whenever the active guard changes.
- Hidden reason text contains no credentials, DSNs, tokens, customer data, or stack details.
- A newly added toolbar action must have focused available, unavailable, and busy-state tests when applicable.

## Verification

The focused application regression checks the exact inaccessible-to-available boundary rather than merely asserting markup:

- unavailable actions expose `aria-disabled="true"`, are not natively disabled, and receive focus;
- `aria-describedby` resolves to the expected rendered reason;
- pointer activation is inert;
- destructive confirmation, relationship inference, group management, cardinality, and export entry points remain untouched;
- layout and undo stay inert while one animation-frame layout step is pending;
- the busy reason and `aria-busy` remain synchronized.

Exact-head typecheck, the complete frontend test and coverage suite, production build, SAST, accessibility review, and browser-level verification remain authoritative.

## Monitoring and rollback

Monitor keyboard abandonment around the canvas toolbar, unexpected action invocation while disabled, repeated clicks on unavailable actions, focus-order length, export/modal invocation errors, and layout double-start attempts. Record action identifiers and state categories only; do not log schema names or other customer content solely for this feature.

Rollback may restore native `disabled` only together with an alternative discoverable prerequisite surface that remains keyboard and screen-reader accessible. Removing the guards without restoring native disabled semantics is prohibited because it would expose state-changing actions while the UI reports them as unavailable.

The repeated JSX, reason-ID, and guard logic is tracked as a separate design-system slice. That refactor must preserve the exact behavior before replacing this implementation.

## References

World Wide Web Consortium. (2025). *Button pattern*. WAI-ARIA Authoring Practices Guide. https://www.w3.org/WAI/ARIA/apg/patterns/button/

World Wide Web Consortium. (2025). *Developing a keyboard interface*. WAI-ARIA Authoring Practices Guide. https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/

World Wide Web Consortium. (2025). *Toolbar pattern*. WAI-ARIA Authoring Practices Guide. https://www.w3.org/WAI/ARIA/apg/patterns/toolbar/

World Wide Web Consortium. (2025). *Tooltip pattern*. WAI-ARIA Authoring Practices Guide. https://www.w3.org/WAI/ARIA/apg/patterns/tooltip/
