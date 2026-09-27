## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2026-08-23 - MySQL SQL Injection False Positive Fix
**Vulnerability:** Bandit flagged B608 for dynamic f-string usage in SQL WHERE clause construction.
**Learning:** SAST tools flag f-strings used for structural components even if inputs are safe placeholders. Dynamic logic should be handled via SQL conditions like `(%s IS NULL OR ...)`.
**Prevention:** Avoid dynamic string formatting for SQL structural components like WHERE clauses. Use fully static SQL query strings with static logic.
