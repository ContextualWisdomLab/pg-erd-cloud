# Search identity and sequential polling contracts

## Decision

Search decoration is derived presentation state. While a normalized query is unchanged, the frontend keeps one `WeakMap` whose keys are the immutable source `TableNodeData` objects. A position-only React Flow update therefore reuses the same decorated `data` object instead of allocating a replacement on every render. Replacing source data or changing the normalized query creates a fresh decoration. The source object is never mutated.

Snapshot polling uses completion-driven `setTimeout`, not `setInterval`. Only one `getSnapshot` request may be in flight for an effect generation. A terminal result may trigger one list refresh; a non-terminal result or a recoverable request error schedules the next attempt only after the current attempt completes. Cleanup invalidates the generation before clearing its pending timer, so late snapshot results, list results, and errors cannot update superseded state.

## Invariants

- Stable normalized query + stable source data object => stable decorated data reference.
- Position-only node updates do not alter decorated data identity.
- Changed source data or changed normalized query => fresh decorated data.
- At most one polling request is active per effect generation.
- Terminal state stops polling.
- Cleanup blocks every asynchronous continuation, including list refresh success and failure.
- Tests use controllable promises to verify reverse completion order and post-unmount behavior.

## Rationale

`WeakMap` keys do not prevent collection of obsolete source objects and expose no enumeration surface, which fits an identity cache scoped to a React render generation. Completion-driven timers prevent overlapping work even when network latency exceeds the nominal polling interval. The generation flag remains necessary because clearing a timer cannot cancel a promise that has already started.

## References (APA 7th)

Ecma International. (2025). *ECMAScript 2025 language specification* (ECMA-262, 16th ed.), §24.3 WeakMap objects. https://262.ecma-international.org/16.0/

WHATWG. (2026). *HTML living standard: Timers*. Retrieved August 6, 2026, from https://html.spec.whatwg.org/multipage/timers-and-user-prompts.html#timers
