# Color radio-group accessibility evidence

## Decision

The Business Group color selector uses the WAI-ARIA radio-group pattern with one radio in the page tab sequence. The checked color receives `tabIndex={0}` and every other color receives `tabIndex={-1}`. Right and Down Arrow move focus and selection to the next color; Left and Up Arrow move to the previous color; navigation wraps at both ends. Native button activation preserves Space and click behavior.

This contract is covered by focused regression tests for checked state, roving tabindex, forward and backward arrow navigation, wrapping, unrelated-key handling, and the no-selection fallback.

## Evidence

The W3C Accessible Rich Internet Applications Authoring Practices Guide specifies that a radio group contains `radio` elements with `aria-checked`, that only one radio participates in the tab sequence, and that arrow keys move focus and selection with wrapping.

Chiou, Alotaibi, and Halfond (2021) empirically evaluated automated detection and localization of keyboard-accessibility failures on real web pages. Their results support treating focus reachability and keyboard activation as executable behavior: this change therefore pairs the W3C interaction contract with focused click, Space, arrow-key, wraparound, and roving-tabindex regressions instead of relying on static ARIA attributes alone.

## Reference

World Wide Web Consortium. (n.d.). *Radio group pattern*. WAI-ARIA Authoring Practices Guide. Retrieved August 4, 2026, from https://www.w3.org/WAI/ARIA/apg/patterns/radio/

World Wide Web Consortium. (n.d.). *Radio group example using roving tabindex*. WAI-ARIA Authoring Practices Guide. Retrieved August 4, 2026, from https://www.w3.org/WAI/ARIA/apg/patterns/radio/examples/radio/

Chiou, P. T., Alotaibi, A. S., & Halfond, W. G. J. (2021). Detecting and localizing keyboard accessibility failures in web applications. In *Proceedings of the 29th ACM Joint Meeting on European Software Engineering Conference and Symposium on the Foundations of Software Engineering* (pp. 855–867). Association for Computing Machinery. https://doi.org/10.1145/3468264.3468581
