# Discoverable disabled form-action contract

## Decision

The Add Table dialog keeps its Save button in the sequential focus order even when a blank or whitespace-only table name makes the action unavailable. The native `disabled` attribute is not used for this product state. Instead, the button exposes `aria-disabled="true"`, uses a visibly unavailable presentation, references a visible explanation, and explicitly suppresses every submission path until the trimmed name is non-empty.

This is a deliberate discoverability contract. A user navigating only by keyboard or an assistive-technology command can reach the action, identify it as unavailable, and read the prerequisite rather than having the action disappear from navigation.

## Standards basis

WAI-ARIA 1.2 defines `aria-disabled` as indicating that an element is perceivable but not editable or otherwise operable. The specification supports `aria-disabled` on the `button` role and requires authors to implement the unavailable behavior in script because ARIA communicates semantics but does not suppress activation itself. It also recommends a visual disabled treatment.

The current WAI-ARIA 1.3 draft retains the same core state definition and continues to support `aria-disabled` for buttons. The implementation follows the stable WAI-ARIA 1.2 contract; the draft is monitored but is not treated as the release baseline.

## Interaction contract

When the trimmed table name is empty:

- Save remains a native `<button type="submit">` and can receive focus.
- `aria-disabled` is `true`.
- the button and name input reference the same visible prerequisite through `aria-describedby`;
- click activation is prevented;
- Enter and Space activation are prevented through the same click boundary;
- direct form submission is prevented by the form-level guard;
- the application callback is never invoked;
- opacity and `not-allowed` pointer presentation reinforce the semantic state.

When the trimmed table name is non-empty:

- `aria-disabled` becomes `false`;
- the temporary prerequisite and description references are removed;
- click, Enter, Space, and native form submission use the existing form contract;
- one activation produces one callback invocation.

## Verification requirements

The exact pull-request head must prove:

- hidden dialog behavior is unchanged;
- blank and whitespace-only names are unavailable;
- the button remains focusable;
- the visible explanation is associated with both the input and Save action;
- click, Enter, Space, and direct submit are inert while unavailable;
- a valid name removes the temporary explanation and submits exactly once;
- cancel and input-change behavior remain unchanged;
- frontend typecheck, the complete coverage-instrumented suite with its exact report, production build, Security Scan, Semgrep, CodeRabbit, and independent current-head review pass;
- package manifests, lockfiles, CI package-manager policy, and unrelated App orchestration tests remain identical to `main`.

## APA 7 references

World Wide Web Consortium. (2023). *Accessible Rich Internet Applications (WAI-ARIA) 1.2*. https://www.w3.org/TR/wai-aria-1.2/

World Wide Web Consortium. (2026). *Accessible Rich Internet Applications (WAI-ARIA) 1.3* [Working Draft]. https://www.w3.org/TR/wai-aria-1.3/
