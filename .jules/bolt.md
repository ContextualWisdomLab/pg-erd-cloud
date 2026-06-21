## 2024-06-21 - [Avoid Map Creation on High-Frequency React Arrays]
**Learning:** React Flow updates the `nodes` array extremely frequently (e.g., during dragging). Creating a `Map` (like `nodesById`) using a `useMemo` that depends on this array forces a full O(N) iteration, memory allocation, and GC on every single micro-update.
**Action:** For standard node lookups in a typically sized ERD (10-500 tables), prefer an O(N) `Array.prototype.find()` without allocating intermediate memory structures over building and looking up a `Map`.
