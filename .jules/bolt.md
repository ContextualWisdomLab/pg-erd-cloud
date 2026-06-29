## 2024-06-21 - [Avoid Map Creation on High-Frequency React Arrays]
**Learning:** React Flow updates the `nodes` array extremely frequently (e.g., during dragging). Creating a `Map` (like `nodesById`) using a `useMemo` that depends on this array forces a full O(N) iteration, memory allocation, and GC on every single micro-update.
**Action:** For standard node lookups in a typically sized ERD (10-500 tables), prefer an O(N) `Array.prototype.find()` without allocating intermediate memory structures over building and looking up a `Map`.
## 2026-06-19 - Endless Polling in React Components
**Learning:** React `useEffect` with `setInterval` for polling can easily become a performance bottleneck (unnecessary network calls, state updates, and potential memory leaks) if the termination condition isn't handled correctly when the polled job reaches a terminal state.
**Action:** Always ensure polling mechanisms have a clean exit strategy by clearing intervals once a terminal state (like `succeeded`, `failed`, or `not_found`) is reached.

## 2026-06-19 - Expensive useMemo Keys
**Learning:** Using `JSON.stringify` on large data objects as a dependency for `useMemo` is an expensive hack to prevent re-renders, causing severe performance issues as the data size grows.
**Action:** Rely on proper reference management and stop unnecessary state updates (like fixing endless polling) instead of using deep stringification hacks for `useMemo` dependencies.
## 2026-06-20 - O(N^2) loops for finding items in export
**Learning:** Nested array `.find()` iterations within loops parsing graph connections result in O(N^2) complexity, significantly degrading UI performance for large outputs.
**Action:** Always pre-compute a lookup `Map` in O(N) when multiple specific node lookups are needed within iterative processes.
## 2024-05-24 - Optimize O(N*M) lookups to O(1) Sets in React state mapping
- **Learning**: Using `array.some(...)` inside `array.map(...)` can become a significant performance bottleneck (O(N*M)) when dealing with large sets of recommendations or nodes.
- **Action**: Always pre-compute a `Set` or dictionary outside the mapping loop for fast O(1) signature-based lookups.
- **Safety**: When moving logic into a state updater callback like `setNodes((currentNodes) => ...)`, make sure to evaluate any validation checks (like checking if an index is already applied) **inside** the callback to prevent stale closures. Avoid unchecked properties like `columns.join` if `columns` could be undefined.
## 2024-06-21 - Optimize O(N^2) Map building
**Learning:** Building Maps inside loops using `map.set(key, [...(map.get(key) || []), item])` leads to O(N^2) complexity and enormous intermediate garbage generation for large datasets.
**Action:** Use an O(1) amortized append instead: pull the list with `.get(key)` and use `.push(item)`. Create the array only when inserting the first item.
2024-05-30 - Bug 11: Timeout should move directly to fallback instead of retrying the same model
Learning: When fixing timeout behavior, ensure the `is_timeout_error` function allows for fallback correctly rather than just erroring out or restricting it based on fail-closed flags when retrying.
Action: Removed the fail-closed prevention condition inside `is_timeout_error` to allow appropriate fallback execution.
