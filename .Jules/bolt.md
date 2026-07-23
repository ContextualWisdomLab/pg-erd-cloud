## 2025-06-27 - [Map Initialization Overhead]
**Learning:** Initializing Maps with `new Map(array.map(...))` creates unnecessary intermediate arrays, consuming memory and triggering garbage collection overhead, especially noticeable when dealing with many nodes.
**Action:** Use a `for...of` loop to directly `map.set()` elements rather than creating an intermediate array of tuples, especially in frequently executed or rendering paths.
## 2026-07-23 - [Array.from GC Overhead in Frontend Generators]
**Learning:** Using `Array.from(string)` to iterate characters (such as when calculating handle IDs per node/column) allocates an intermediate array and creates excessive garbage collection pressure during high-frequency frontend updates.
**Action:** Use a `for...of` loop on the string to directly concatenate the result without allocating an array, reducing memory footprint and avoiding GC overhead in hot rendering paths.
