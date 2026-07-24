## 2025-06-27 - [Map Initialization Overhead]
**Learning:** Initializing Maps with `new Map(array.map(...))` creates unnecessary intermediate arrays, consuming memory and triggering garbage collection overhead, especially noticeable when dealing with many nodes.
**Action:** Use a `for...of` loop to directly `map.set()` elements rather than creating an intermediate array of tuples, especially in frequently executed or rendering paths.
## $(date +%Y-%m-%d) - [O(1) Dictionary Lookup for DBML parsing]
**Learning:** O(n^2) complexity from inline generator expressions (e.g., `sum(1 for ...)` inside loops) used to calculate positions or occurrences in DBML import operations.
**Action:** Use an auxiliary O(1) dictionary counter instead.
