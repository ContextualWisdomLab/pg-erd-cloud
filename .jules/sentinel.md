## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2026-08-07 - Fix SQL Injection in MySQL Introspection
**Vulnerability:** MySQL introspection queries were dynamically constructed via f-strings for the WHERE clause.
**Learning:** Dynamic query construction, even if seemingly safe via sub-functions returning parameterized strings, creates SQL injection risks. Queries should be entirely static and parameterization applied consistently.
**Prevention:** Use static query logic like WHERE (%s IS NULL OR ...) to rely entirely on standard driver parameterization and eliminate dynamic query formatters.
