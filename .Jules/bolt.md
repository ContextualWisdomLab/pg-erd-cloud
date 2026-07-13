## 2025-06-27 - [Map Initialization Overhead]
**Learning:** Initializing Maps with `new Map(array.map(...))` creates unnecessary intermediate arrays, consuming memory and triggering garbage collection overhead, especially noticeable when dealing with many nodes.
**Action:** Use a `for...of` loop to directly `map.set()` elements rather than creating an intermediate array of tuples, especially in frequently executed or rendering paths.

## 2024-07-13 - Optimize Data Dictionary Export Algorithm
**Learning:** Found an O(N * C * E) bottleneck in `frontend/src/erd/exportDataDictionary.ts` where `isForeignKeyColumn` did an `edges.some()` search per column inside a loop over nodes and columns.
**Action:** When writing complex export algorithms over a large graph (Nodes + Edges), always pre-compute search spaces using Maps or Sets (e.g. `fkHandles`) upfront (O(E)) to achieve O(1) lookups during deeply nested loops (O(N * C + E)).
