## 2025-06-27 - [Map Initialization Overhead]
**Learning:** Initializing Maps with `new Map(array.map(...))` creates unnecessary intermediate arrays, consuming memory and triggering garbage collection overhead, especially noticeable when dealing with many nodes.
**Action:** Use a `for...of` loop to directly `map.set()` elements rather than creating an intermediate array of tuples, especially in frequently executed or rendering paths.

## 2025-07-19 - [Array.from string allocation overhead]
**Learning:** Using `Array.from(string)` creates unnecessary intermediate array allocations, causing performance regressions and garbage collection overhead during high-frequency loop operations (like generating string IDs or handles for rendering and exporting).
**Action:** Use a `for...of` loop or standard string iteration to construct strings sequentially instead of allocating and joining arrays when operating on individual characters.
