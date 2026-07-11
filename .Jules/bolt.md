## 2025-06-27 - [Map Initialization Overhead]
**Learning:** Initializing Maps with `new Map(array.map(...))` creates unnecessary intermediate arrays, consuming memory and triggering garbage collection overhead, especially noticeable when dealing with many nodes.
**Action:** Use a `for...of` loop to directly `map.set()` elements rather than creating an intermediate array of tuples, especially in frequently executed or rendering paths.

## 2025-06-27 - [High-Frequency Array Allocation in Render Loops]
**Learning:** Using `flatMap().join()` on arrays in a React render cycle (like high-frequency ERD search filtering inside `useMemo`) creates severe Garbage Collection pressure and performance bottlenecks compared to direct string concatenation due to intermediate array allocations.
**Action:** Use direct string concatenation with `+=` inside loops for heavy filtering operations to prevent excessive GC loads.
