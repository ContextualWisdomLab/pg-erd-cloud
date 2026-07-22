## 2025-06-27 - [Map Initialization Overhead]
**Learning:** Initializing Maps with `new Map(array.map(...))` creates unnecessary intermediate arrays, consuming memory and triggering garbage collection overhead, especially noticeable when dealing with many nodes.
**Action:** Use a `for...of` loop to directly `map.set()` elements rather than creating an intermediate array of tuples, especially in frequently executed or rendering paths.
## 2024-07-22 - O(N^2) complexity in DBML import
**Learning:** Found an O(N^2) complexity issue in the DBML import parser where it was using an inline generator expression (`sum(1 for ...)`) to calculate the column position by iterating over all previously parsed columns.
**Action:** Replaced the inline loop with an auxiliary O(1) dictionary counter (`col_count_by_oid`) to keep a running tally of column positions.
