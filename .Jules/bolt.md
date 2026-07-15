## 2025-06-27 - [Map Initialization Overhead]
**Learning:** Initializing Maps with `new Map(array.map(...))` creates unnecessary intermediate arrays, consuming memory and triggering garbage collection overhead, especially noticeable when dealing with many nodes.
**Action:** Use a `for...of` loop to directly `map.set()` elements rather than creating an intermediate array of tuples, especially in frequently executed or rendering paths.
## 2025-07-15 - [O(N^2) Array Searches in Edge Handling]
**Learning:** Using `Array.find()` multiple times inside an iteration (like finding columns corresponding to an edge's source/target handle) across large node graphs scales poorly (O(N^2)) and slows down export operations.
**Action:** Replace `Array.find()` with direct iteration and early breaking (`break`), or a single pass lookup map for frequent lookups on the same data.
