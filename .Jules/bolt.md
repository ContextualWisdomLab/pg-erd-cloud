## 2025-06-27 - [Map Initialization Overhead]
**Learning:** Initializing Maps with `new Map(array.map(...))` creates unnecessary intermediate arrays, consuming memory and triggering garbage collection overhead, especially noticeable when dealing with many nodes.
**Action:** Use a `for...of` loop to directly `map.set()` elements rather than creating an intermediate array of tuples, especially in frequently executed or rendering paths.

## $(date +%Y-%m-%d) - O(N^2) DBML Parsing Bottleneck
**Learning:** In `backend/app/spec/dbml_import.py`, assigning column position numbers using an inline generator expression (`sum(1 for c in columns if c["relation_oid"] == oid)`) inside a parsing loop creates an O(N^2) bottleneck. For schemas with thousands of columns, this takes seconds.
**Action:** Always use an auxiliary O(1) dictionary counter (`col_count_by_table.setdefault(oid, 0) + 1`) to track occurrences within loops to reduce complexity from O(N^2) to O(N).
