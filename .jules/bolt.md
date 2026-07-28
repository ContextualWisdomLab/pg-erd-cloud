## 2025-02-18 - Optimize Handle Resolution in ERD Exports
**Learning:** Checking relationships in ERD exports involved generating heavily modified strings for every column (via `sourceColumnHandleId` / `sanitizeHandleId`) to match against edge handle IDs. This $O(N)$ operation inside an edge loop caused excessive string allocations and garbage collection overhead.
**Action:** Implemented an $O(1)$ `parseColumnNameFromHandle` utility to directly extract and decode the column name from the handle ID, preventing the need to iterate through and encode all node columns.
