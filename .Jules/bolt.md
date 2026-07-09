## 2025-06-27 - [Map Initialization Overhead]
**Learning:** Initializing Maps with `new Map(array.map(...))` creates unnecessary intermediate arrays, consuming memory and triggering garbage collection overhead, especially noticeable when dealing with many nodes.
**Action:** Use a `for...of` loop to directly `map.set()` elements rather than creating an intermediate array of tuples, especially in frequently executed or rendering paths.

## $(date +%Y-%m-%d) - Optimize Search Array Operations in React
**Learning:** High-frequency `useMemo` hooks calculating search filter matches across large nested structures (like React Flow nodes and their columns) generate severe garbage collection pressure when using array methods (`map`, `flatMap`, `spread operator` and `join`).
**Action:** For string search haystacks calculated inside hot paths, replacing functional array map/spreads with standard `for` loops and direct string concatenation (`+=`) drastically reduces intermediate memory allocations and maintains stable performance during frequent text input.
