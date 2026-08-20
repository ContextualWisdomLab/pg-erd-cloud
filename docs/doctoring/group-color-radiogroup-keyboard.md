# Doctoring record: business-group color radiogroup

## Decision

The business-group color chooser is one composite single-selection control. Its container uses `role="radiogroup"`; every color swatch uses `role="radio"` and exposes selection through `aria-checked`.

The checked color is the only swatch in the page Tab sequence. The other swatches use `tabIndex={-1}`. Arrow Right and Arrow Down move to the next color; Arrow Left and Arrow Up move to the previous color. Movement wraps at both ends, moves DOM focus, and updates the selected color together. Pointer activation continues to select the clicked color.

When the stored color is not represented in the current palette, the first swatch becomes the safe Tab stop while no unsupported value is silently rewritten merely by rendering the modal.

## Buyer impact

Keyboard and assistive-technology users can enter the color chooser once, inspect the current selection, and traverse the palette without tabbing through every decorative swatch. The chosen state and keyboard focus cannot diverge during arrow-key operation.

## Standards rationale

The WAI-ARIA Authoring Practices radio-group pattern treats a radio group as a composite widget. In the checked state, Tab enters the group at the checked radio; arrow keys move focus and check the adjacent radio, with wrapping at the ends. Roving `tabindex` provides one sequential keyboard stop while preserving direct focus movement inside the group.

This component follows the no-toolbar radio pattern. Space activation remains provided by the native button element; the added arrow-key handling does not suppress Tab, Enter, Escape, or unrelated keys.

The implementation is a component-level accessibility contract. It does not by itself prove whole-product WCAG conformance, visual color distinguishability, forced-colors behavior, screen-reader interoperability, or the semantic suitability of each palette value.

## Verification contract

`frontend/src/components/modals/GroupModal.radiogroup.test.tsx` renders the real controlled component and proves that:

- all palette choices expose the radio role;
- exactly the checked choice has `tabindex="0"`;
- every unchecked choice has `tabindex="-1"`;
- Arrow Right and Arrow Down select and focus the next choice;
- Arrow Left and Arrow Up select and focus the previous choice;
- traversal wraps from the final choice to the first choice;
- Tab from the group-name field lands on the checked radio, and the next Tab leaves the group once;
- Space on a focused radio checks that radio; and
- the checked radio matches `.groupManager__swatch[aria-checked="true"]`, which is the selected-state selector in `GroupModal.css`.

The pre-implementation test-only head `8d81b7629081ecfbb3064467ecd1374f81391184` failed all six focused cases on hosted CI because the original implementation had no roving `tabindex` and no arrow-key behavior. The production repair was then applied in `5a9793976ef55716bd3d56ebddcc59fd8044d5db`.

## Compatibility and rollback

No database, API, persistence, palette color values, group-creation rule, or assignment behavior changes. The selected swatch now uses `aria-checked="true"` with a 3px tokenized `box-shadow` (`--color-text-strong`) in `GroupModal.css` (and the matching global selector) so the checked ring remains visible after the role change from `aria-pressed`. Palette hex values themselves are unchanged. Rollback would restore mismatched radio semantics in which every native button remained a separate Tab stop and arrow keys did not operate the group; therefore rollback must revert the radio role, the selected-state selector, and the keyboard contract together rather than retaining a partially implemented composite widget.

## References

World Wide Web Consortium Web Accessibility Initiative. (2025). *Radio group pattern*. WAI-ARIA Authoring Practices Guide. https://www.w3.org/WAI/ARIA/apg/patterns/radio/

World Wide Web Consortium Web Accessibility Initiative. (2025). *Radio group example using roving tabindex*. WAI-ARIA Authoring Practices Guide. https://www.w3.org/WAI/ARIA/apg/patterns/radio/examples/radio/

World Wide Web Consortium. (2023, October 5). *Web Content Accessibility Guidelines (WCAG) 2.2* (W3C Recommendation). https://www.w3.org/TR/WCAG22/

World Wide Web Consortium. (2026, June 4). *Accessible Rich Internet Applications (WAI-ARIA) 1.3* (W3C Working Draft). https://www.w3.org/TR/wai-aria-1.3/
