# Search identity and sequential snapshot polling

## Decision

The ERD canvas treats the immutable `TableNodeData` object as the identity of the source table payload. While a normalized search query is active, a query-scoped `WeakMap<TableNodeData, TableNodeData>` stores the derived highlight/dim payload. Re-rendering with the same source object reuses the exact derived reference; changing the normalized query replaces the cache, and replacing the source payload produces a new derived object.

The search matcher independently memoizes one lower-cased searchable text value per immutable `TableNodeData` identity. Title, table comment, column name, data type, and column comment are read only on the first search for that object. Position-only React Flow updates reuse the cached value. Any searchable content change must replace the top-level data object and the changed nested column object; TypeScript `readonly` and `ReadonlyArray` declarations make that contract visible to consumers. If future integration requires mutable data, identity memoization must be replaced with an explicit revision or content-fingerprint invalidation key before mutation is permitted.

Snapshot status polling is one sequential asynchronous process per active `(selectedProjectId, snapshotId)` effect. The first request starts immediately. A non-terminal response schedules one `setTimeout` only after the request completes. Terminal states stop polling and may refresh the snapshot list. Cleanup marks the process obsolete and clears the pending timeout, so late success, refresh, or rejection continuations cannot update the current view.

## Why

React Flow can emit frequent position-only node updates. Reallocating every derived `node.data` object during those updates defeats reference-sensitive memoization below the canvas and creates garbage unrelated to actual table-content changes. Rebuilding the searchable text also repeats a complete column traversal and allocates the same lower-cased strings. `WeakMap` keys use object identity and do not keep otherwise unreachable key objects alive, which fits caches whose lifetime follows the immutable source payload.

Memoization reuses a function result for an input already observed. Michie's foundational description frames this as a program improving execution efficiency by retaining prior results. Here the memoized value is deterministic and contains no external state: it is derived solely from one immutable table-data identity. The cache is an optimization only; replacing the identity recomputes the same search semantics.

A fixed `setInterval` can start another request while the prior request is unresolved. Network responses are not guaranteed to complete in issue order, so an older non-terminal result can overwrite a newer terminal result. React's effect guidance explicitly recommends cleanup-scoped invalidation for manually fetched data because responses may arrive out of order. Completion-scheduled `setTimeout` polling additionally guarantees at most one in-flight status request per effect generation.

## Invariants

- The source `node.data` object and nested searchable column objects are immutable.
- Equivalent normalized queries and position-only updates reuse the derived data reference.
- Repeated searches of the same data identity do not reread searchable fields.
- A changed query or changed source data object yields a fresh derived/searchable value.
- Title, table comment, column name, data type, and column comment replacements all invalidate by identity.
- The memoized searchable text never includes runtime selection, position, secret, credential, or network state.
- At most one `getSnapshot` call is in flight for one effect generation.
- `succeeded`, `failed`, and `not_found` stop future status requests.
- Dependency change or unmount invalidates all pending continuations before they can publish snapshot, list, or error state.
- Polling errors remain visible only for the still-current snapshot process.

## Verification

`frontend/src/App.searchPolling.test.tsx` observes the `ReactFlow` node payload rather than implementation internals. It asserts reference identity with `toBe`, drives a position-only update and a source-data replacement, exercises reversed response order, rejects a superseded request with sensitive detail, and uses controlled timers to prove non-overlap and terminal shutdown.

`frontend/src/erd/__tests__/search.test.ts` uses accessor-observed fixture objects rather than a production counter. It proves the first search reads searchable fields, 100 repeated searches of the same identity read none again, a replacement identity is rebuilt, every searchable field replacement changes results, and a fixed 1,000-node × 20-column workload performs no second-pass field reads. The representative test is deterministic and intentionally does not assert wall-clock time on a shared runner.

Repository CI remains authoritative for npm-only type checking, complete statement/branch/function/line coverage, and the production build.

## Operational monitoring and rollback

Monitor search evaluations, cache-build count in development telemetry, node/column dimensions, browser memory growth, long-task duration during search/drag sessions, snapshot-status request concurrency, terminal-to-render latency, stale-response suppression, and frontend error rates. Do not emit customer schema names or comments merely to observe cache performance.

Roll back searchable-text memoization by restoring field-by-field evaluation only if a verified mutable-data integration cannot first adopt immutable replacement or an explicit revision key. Roll back polling or derived-data identity independently. Any rollback reopens the documented allocation or race risk and therefore requires replacement regression evidence.

## References

Ecma International. (2026). *ECMAScript 2026 language specification* (ECMA-262, 17th ed.). https://262.ecma-international.org/

MDN Web Docs contributors. (2026). *WeakMap*. Mozilla. https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/WeakMap

Michie, D. (1968). “Memo” functions and machine learning. *Nature, 218*, 19–22. https://doi.org/10.1038/218019a0

React Team. (n.d.). *useEffect*. React. Retrieved August 7, 2026, from https://react.dev/reference/react/useEffect

Web Hypertext Application Technology Working Group. (2026, July 13). *HTML Standard: Timers*. https://html.spec.whatwg.org/multipage/timers-and-user-prompts.html#timers
