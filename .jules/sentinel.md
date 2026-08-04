## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2025-02-18 - Hardening Secondary DTOs Against Control Characters
**Vulnerability:** Secondary DTO string fields (like diagram view names, annotation schemas/relations, and API key names) lacked strict validation against control characters.
**Learning:** Even if primary models (like Projects) are secured, missing validation on secondary API endpoints can still expose the application to control character injections (like CRLF injection in logs or null-byte issues).
**Prevention:** Always apply explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` to all user-provided Pydantic string fields across the entire schema suite.
