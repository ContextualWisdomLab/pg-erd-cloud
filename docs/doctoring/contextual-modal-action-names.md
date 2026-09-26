# Contextual modal action names

## Status

Implemented for relationship deletion and table deletion/duplication actions.

## Customer outcome

A screen-reader or speech-input user can distinguish which relationship or
table a generic modal action will affect before activating it. The visible
button copy remains compact, while the accessible name includes the trimmed
entity label. When that label is empty or whitespace-only, the stable edge or
node identifier preserves the target context instead of collapsing to a generic
operation name.

## Accessibility contract

- the accessible name retains the visible operation text, satisfying WCAG 2.2
  Success Criterion 2.5.3 (Label in Name);
- `aria-label` supplies the author-provided name supported by the native button
  role under WAI-ARIA 1.2;
- the target label is normalized only for selecting a non-empty name; customer
  text is otherwise preserved exactly;
- a stable object identifier is the fail-closed fallback;
- visible copy, confirmation, mutation, duplicate construction, and modal
  lifecycle behavior are unchanged.

## Verification

Focused component tests cover:

- relationship labels with normal, empty, and whitespace-only values;
- table titles with normal, empty, and whitespace-only values;
- deletion and duplication action lookup by complete accessible name;
- unchanged relationship confirmation and table mutation behavior.

Exact-head frontend type checking, complete tests, coverage, production build,
and automated accessibility/security review remain release gates.

## Monitoring and rollback

Monitor failed accessible-name queries in component and end-to-end tests. A
rollback restores the preceding release as a whole; do not remove the stable-ID
fallback or replace the contextual name with a tooltip-only explanation.

## References

World Wide Web Consortium. (2024, December 12). *Web Content Accessibility
Guidelines (WCAG) 2.2* (W3C Recommendation).
https://www.w3.org/TR/WCAG22/

World Wide Web Consortium. (2023, June 6). *Accessible Rich Internet
Applications (WAI-ARIA) 1.2* (W3C Recommendation).
https://www.w3.org/TR/wai-aria-1.2/

World Wide Web Consortium. (2026, May 20). *Accessible Name and Description
Computation 1.2* (W3C Working Draft).
https://www.w3.org/TR/2026/WD-accname-1.2-20260520/
