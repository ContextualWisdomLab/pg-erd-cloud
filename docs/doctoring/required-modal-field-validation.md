# Required modal field validation

## Buyer problem

Several modal forms displayed a visual required marker while the executable constraint did not match it. In particular, relationship labels and business-group names could contain only whitespace: HTML `required` treats the empty string as missing, but whitespace is still a non-empty value. That mismatch made the UI promise stricter validation than the form actually enforced.

## Product contract

- Native `required` remains the semantic baseline for every mandatory text input in this slice.
- Relationship labels and business-group names additionally reject whitespace-only values before the mutation callback runs.
- Empty relationship and group names receive the same actionable Korean guidance through the input's native invalid event; whitespace-only values receive equivalent guidance through the explicit trim guard.
- The business-group form also renders linked guidance while its Add action is disabled, so the customer can see the next action without needing to trigger an unavailable submit control.
- Changing either value clears the stale custom validity message immediately.
- The visual `*` is centralized in `RequiredIndicator`, uses the existing `--color-danger` token, and is `aria-hidden="true"` because the input itself carries the required semantics.
- No API, database, persistence, authorization, or deployment contract changes.

## Design and accessibility authority

Fresh Figma evidence on 2026-08-30 confirms file `csnpEEJfmqFWB0vNUoTkWA`, page `190:2` (`Design System — Storybook Contract`), frame `190:40` (`Design Token Authority`), including `--color-danger = #b91c1c` and the instruction to change runtime source first, keep Storybook exact-value tests green, then resync Figma. The paired executable Storybook token inventory is currently owned by PR #944 at exact head `ffcf653e78306563797262678a4313c8215a5932` and renders exact token values as text while marking decorative previews `aria-hidden`.

This PR reuses that shared token contract rather than adding a local color. It does not claim a current Storybook component-state story for required-field validation: the protected base does not yet contain #944. Therefore design acceptance remains fail-closed until the required-field state is represented against the then-current paired Figma and Storybook authority before merge.

## Verification

Focused tests pin semantic `required` state for add-table, relationship, group, table-title, column-name, and column-type inputs; empty and whitespace-only validation guidance; whitespace-only mutation blocking; linked visible group guidance; clearing stale custom validity; and the decorative marker's exclusion from the accessibility tree. Existing modal coverage continues to exercise valid submit/cancel/delete flows.

## Standards traceability

The HTML Standard defines `required` as a boolean constraint and treats a required mutable input whose value is the empty string as missing. The same standard exposes `setCustomValidity()` and `reportValidity()` for constraints beyond the native empty-string rule. WAI-ARIA 1.2 specifies that elements with `aria-hidden="true"` should not be included in the accessibility tree; the marker is non-focusable decoration, not the semantic source of required state.

### References

WHATWG. (2026). *HTML Standard*. Retrieved August 30, 2026, from https://html.spec.whatwg.org/

World Wide Web Consortium. (2023). *Accessible Rich Internet Applications (WAI-ARIA) 1.2* (W3C Recommendation, June 6, 2023). https://www.w3.org/TR/wai-aria-1.2/
