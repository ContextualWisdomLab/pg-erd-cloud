# Native form submission and search behavior

## Status

Implemented in the authenticated React application. This is an accessibility
and interaction contract, not a conformance certification.

## Creation forms

The editor project creator, project-list inline creator, and editor connection
creator are semantic HTML `form` elements. Their action buttons use
`type="submit"`; click and Enter therefore converge on the same handler rather
than dispatching duplicate request paths.

Each submit handler prevents browser navigation and calls the existing async
operation. Production guards remain authoritative:

- trimmed empty project names never call the API;
- a connection requires a selected project, non-empty name and secret DSN;
- the DSN must satisfy the existing PostgreSQL/Postgres/Snowflake URL policy;
- the password field is cleared before any connection request and after an
  invalid DSN, so the secret is not retained in React state; and
- `isCreatingProject` and `isCreatingConnection` prevent a second Enter or
  click while the first request is active.

Native required-field attributes were not introduced because the product's
existing disabled-state, contextual-hint, trimming, and DSN policy provide the
current validation contract. This change does not alter DSN authority,
authentication, API payloads, polling, status rendering, or dependencies.

## Search forms

Diagram and canvas search controls are semantic forms with `role="search"`.
Their submit handler only calls `preventDefault()`. Enter therefore cannot
navigate or reload the page, while the controlled input and existing live
filter remain unchanged. The accessible labels and visible layout are
preserved.

## Failure and recovery

API failures continue through the existing application error boundary. A
failed operation re-enables its submit control in `finally`, allowing a
corrected retry. Invalid connection input is rejected before API access. Search
submission has no durable side effect and needs no recovery procedure.

## Acceptance evidence

`frontend/src/App.coverage.test.tsx` uses real keyboard events against rendered
application forms. It proves whitespace-only project rejection, exact-once
editor and project-list Enter submission, invalid DSN rejection and secret
clearing, exact-once connection submission, async re-entry blocking, semantic
search roles, and preserved live filtering. Existing click tests prove that
pointer activation uses the same path.

## References

Web Hypertext Application Technology Working Group. (2026). *HTML living
standard: Forms*. https://html.spec.whatwg.org/multipage/forms.html

World Wide Web Consortium. (2023). *Web Content Accessibility Guidelines
(WCAG) 2.2: Guideline 2.1 keyboard accessible*.
https://www.w3.org/TR/WCAG22/#keyboard-accessible
