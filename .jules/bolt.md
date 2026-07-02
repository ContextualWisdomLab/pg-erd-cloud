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

## 2026-06-25 - Avoid Redundant map.set() on Mutable Map Values
**Learning:** When updating mutable values stored in a `Map`, such as `Set` or `Array`, calling `map.set(key, value)` after every mutation repeats work once the entry already exists.
**Action:** Create and store the mutable value only when `map.get(key)` misses. After that, mutate the retrieved collection directly with `.add()` or `.push()`.
## Performance Issue: Inefficient Route Metric Priming
The previous implementation of `prime_http_metrics` resulted in an O(M * R) Cartesian product loop creating metric series for every HTTP method across every single route.

## Fix
Optimized metric route processing to O(N) by creating a mapping of routes directly to their active methods and iterating solely over those active methods.

## Benchmark Results
100 unique routes, 1 unique method each (100 total combinations):
- Before: ~820.62ms
- After: ~1.17ms
## 2026-06-25 - Avoid unbounded Math.min/Math.max spreads
**Learning:** Spreading dynamically sized arrays into variadic functions like `Math.max(...values)` creates intermediate arrays and can exceed JS engine argument-count limits, often surfacing as `RangeError` variants such as "Too many arguments".
**Action:** For unbounded frontend collections such as ERD nodes, calculate min/max bounds with an iterative loop instead of `Math.min(...array)` or `Math.max(...array)`.

## 2024-07-01 - Avoid O(N^2) Complexity in Graph Exporters
**Learning:** Nested array `.find()` or `.some()` iterations within loops parsing graph connections result in O(N^2) complexity, significantly degrading UI performance for large outputs (like exporting Mermaid diagrams where we check every column of every node against every edge).
**Action:** Always pre-compute a lookup `Map` or `Set` in O(N) or O(E) when multiple specific node or edge lookups are needed within iterative processes.
