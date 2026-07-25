## 2025-06-27 - [Map Initialization Overhead]
**Learning:** Initializing Maps with `new Map(array.map(...))` creates unnecessary intermediate arrays, consuming memory and triggering garbage collection overhead, especially noticeable when dealing with many nodes.
**Action:** Use a `for...of` loop to directly `map.set()` elements rather than creating an intermediate array of tuples, especially in frequently executed or rendering paths.
## 2024-07-20 - Avoid O(N^2) complexity with inline generator expressions used for counting
**Learning:** Using an inline generator expression like `sum(1 for c in columns if c["relation_oid"] == oid) + 1` inside a loop evaluating DBML columns creates O(N^2) complexity, causing significant slowdowns as the number of columns increases.
**Action:** Replace inline generator expressions used for positioning/counting inside loops with an auxiliary O(1) dictionary counter (e.g. `counts_by_oid[oid] = counts_by_oid.get(oid, 0) + 1`) to keep iteration complexity at O(N).
