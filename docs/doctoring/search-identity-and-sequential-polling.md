# Search identity and sequential snapshot polling

## Decision

The ERD canvas treats the immutable `TableNodeData` object as the identity of the source table payload. While a normalized search query is active, a query-scoped `WeakMap<TableNodeData, TableNodeData>` stores the derived highlight/dim payload. Re-rendering with the same source object reuses the exact derived reference; changing the normalized query replaces the cache, and replacing the source payload produces a new derived object.

Snapshot status polling is one sequential asynchronous process per active `(selectedProjectId, snapshotId)` effect. The first request starts immediately. A one-second interval may trigger a poll, but the `isPolling` guard prevents overlap until the current request completes. Terminal states clear the interval and may refresh the snapshot list. Cleanup marks the process obsolete and clears the interval, so late success, refresh, or rejection continuations cannot update the current view.

## Why

React Flow can emit frequent position-only node updates. Reallocating every derived `node.data` object during those updates defeats reference-sensitive memoization below the canvas and creates garbage unrelated to actual table-content changes. `WeakMap` keys use object identity and do not keep otherwise unreachable key objects alive, which fits a cache whose lifetime follows the source payload.

A fixed `setInterval` can start another request while the prior request is unresolved. The local `isPolling` guard prevents that overlap. Network responses are not guaranteed to complete in issue order, so an older non-terminal result can overwrite a newer terminal result. React's effect guidance explicitly recommends cleanup-scoped invalidation for manually fetched data because responses may arrive out of order. Cleanup invalidation and the terminal guard ensure at most one active status request can publish state for an effect generation.

## Invariants

- The source `node.data` object is never mutated with search-only state.
- Equivalent normalized queries and position-only updates reuse the derived data reference.
- A changed query or changed source data object yields a fresh derived reference.
- At most one `getSnapshot` call is in flight for one effect generation.
- `succeeded`, `failed`, and `not_found` stop future status requests.
- Dependency change or unmount invalidates all pending continuations before they can publish snapshot, list, or error state.
- Polling errors remain visible only for the still-current snapshot process.

## Verification

`frontend/src/App.searchPolling.test.tsx` observes the `ReactFlow` node payload rather than implementation internals. It asserts reference identity with `toBe`, drives a position-only update and a source-data replacement, exercises reversed response order, rejects a superseded request with sensitive detail, and uses controlled timers to prove non-overlap and terminal shutdown. Repository CI remains authoritative for npm-only type checking, complete statement/branch/function/line coverage, and the production build.

## Operational monitoring and rollback

Monitor snapshot-status request concurrency, terminal-to-render latency, stale-response suppression, browser memory growth during long search/drag sessions, and frontend error rates. Roll back by restoring the prior uncached derivation and interval loop only if a verified regression requires it; doing so reopens the documented allocation and race risks and therefore requires a replacement isolation design and regression evidence.

## References

MDN Web Docs contributors. (2026). *WeakMap*. Mozilla. https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/WeakMap

React Team. (n.d.). *useEffect*. React. Retrieved August 7, 2026, from https://react.dev/reference/react/useEffect

Web Hypertext Application Technology Working Group. (2026, July 13). *HTML Standard: Timers*. https://html.spec.whatwg.org/multipage/timers-and-user-prompts.html#timers
