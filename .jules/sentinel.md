## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters (Extended)
**Vulnerability:** User-provided string fields in API payload schemas (`DiagramViewCreateIn`, `TableAnnotationUpsertIn`, `ApiKeyCreateIn`) lacked strict validation against control characters.
**Learning:** These fields can be susceptible to log injection or null byte injection similar to previously identified issues in project and connection names. The use of regex (`pattern=r"^[^\x00-\x1F\x7F]+$"`) must be universally applied across all user-facing string inputs.
**Prevention:** Apply `pattern=r"^[^\x00-\x1F\x7F]+$"` on all relevant Pydantic string fields consistently throughout the application to strictly reject control characters.
