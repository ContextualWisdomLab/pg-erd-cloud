## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2026-09-20 - Unbounded Cache Allocation in handleUtils
**Vulnerability:** The `sanitizeHandleId` LRU cache accepted unbounded string lengths and arbitrary characters without validation, leading to potential memory exhaustion (DoS) and cache pollution.
**Learning:** When creating unbounded or poorly bounded LRU caches based on user input, it's critical to validate the inputs' size and content before performing expensive allocations or caching operations.
**Prevention:** Apply strict length enforcement and regex whitelisting on user inputs before caching or iterating over them. Avoid non-null assertions on string code points.
