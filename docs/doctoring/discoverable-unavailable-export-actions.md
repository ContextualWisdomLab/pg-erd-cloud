# Discoverable unavailable export actions

## Decision

Share-link creation, export, and access-management actions that are unavailable because a prerequisite is missing remain ordinary focusable HTML buttons. They expose `aria-disabled="true"` and reference the visible prerequisite message with `aria-describedby`. The component suppresses pointer, Enter, and Space activation while unavailable. When the prerequisite exists, `aria-disabled` is omitted and the original callback runs.

This differs deliberately from the native `disabled` attribute. Native disabled controls are removed from the sequential focus order in common browser behavior, which can make the action catalogue and the reason for unavailability difficult to discover for keyboard and screen-reader users. `aria-disabled` communicates an inoperable state without providing behavior; the application therefore owns both event suppression and a visible unavailable style.

A short-lived busy state is a different contract from a missing prerequisite. While a share link is actively being created, the create button remains natively `disabled` with `aria-busy="true"` to suppress duplicate submission. When creation is unavailable only because no project is selected, the button remains focusable and is described by the visible next action, “먼저 프로젝트를 선택하세요.”

## Scope and invariants

- Every unavailable export format remains reachable by Tab.
- Share-link creation remains reachable by Tab when no project is selected and exposes the project-selection prerequisite through `aria-describedby`.
- The state is perceivable through `aria-disabled` and the same visible explanation is programmatically associated through `aria-describedby`.
- Click, Enter, and Space cannot invoke an unavailable callback.
- Keyboard suppression does not interfere with Tab navigation.
- Available actions omit `aria-disabled` and preserve their existing activation behavior.
- The access-management placeholder follows the same focusable, described, inert contract.
- The transient share-link creation busy state remains natively disabled and exposes `aria-busy` so repeated activation cannot start duplicate work.
- No export permission, sharing permission, serialization, download, or data-readiness rule is weakened.

## Verification

Focused component tests enumerate all eight unavailable export actions and assert DOM-level focusability, `aria-disabled="true"`, the descriptive relationship, pointer and keyboard inertness, and restoration of normal callback behavior when available. A dedicated share-link regression asserts the same discoverable/inert contract when no project is selected, while the existing busy-state test preserves native disabling during active creation. The complete frontend typecheck, 100% statement/branch/function/line coverage suite, production build, security scans, and exact-head independent review remain mandatory.

## Monitoring and rollback

Monitor keyboard-only completion, support requests about unavailable sharing or exports, accidental callback invocation, duplicate share-link creation, and accessibility-regression results. Rollback must not silently remove the explanation from keyboard access; a replacement design must preserve discoverability, explicit inertness, and the distinction between prerequisite-missing and actively-busy states.

## Standards status

WAI-ARIA 1.2 is the published normative baseline used here. WAI-ARIA 1.3 remains under development and is monitored as a draft, not treated as a final standard.

The user-study evidence below supports the broader product rationale for making an unavailable or inaccessible action and its reason discoverable. It does not by itself validate this specific `aria-disabled` implementation; the normative state semantics remain governed by WAI-ARIA and the repository's executable component tests.

## References

World Wide Web Consortium. (2023). *Accessible Rich Internet Applications (WAI-ARIA) 1.2*. https://www.w3.org/TR/wai-aria-1.2/

World Wide Web Consortium. (2026). *Accessible Rich Internet Applications (WAI-ARIA) 1.3* (Working Draft). https://www.w3.org/TR/wai-aria-1.3/

Bigham, J. P., Lin, I., & Savage, S. (2017). The effects of “not knowing what you don’t know” on web accessibility for blind web users. In *Proceedings of the 19th International ACM SIGACCESS Conference on Computers and Accessibility* (pp. 101–109). Association for Computing Machinery. https://doi.org/10.1145/3132525.3132533

Research relevance: In a study of 30 blind and 30 sighted web users, uncertainty about whether task-relevant information was absent, inaccessible, or merely difficult to locate caused frustration and wasted time. That finding supports exposing an unavailable action together with an explicit prerequisite or recovery explanation instead of making the action silently undiscoverable.
