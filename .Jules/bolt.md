## 2025-06-27 - [Map Initialization Overhead]
**Learning:** Initializing Maps with `new Map(array.map(...))` creates unnecessary intermediate arrays, consuming memory and triggering garbage collection overhead, especially noticeable when dealing with many nodes.
**Action:** Use a `for...of` loop to directly `map.set()` elements rather than creating an intermediate array of tuples, especially in frequently executed or rendering paths.
## 2024-07-20 - String Iteration Performance
**Learning:** For high-frequency string operations in the frontend (e.g., generating handle IDs for nodes/edges), avoid using `Array.from(string)` as it creates intermediate array allocations and increases garbage collection overhead.
**Action:** Use a `for...of` loop or standard string iteration to avoid intermediate allocations and reduce garbage collection pressure.
