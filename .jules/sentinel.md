## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters (Continued)
**Vulnerability:** User-provided string fields for diagram views, API keys, and table annotations lacked strict validation against control characters.
**Learning:** This extends the log injection and terminal escape vulnerability surface to these additional API endpoints.
**Prevention:** Apply the `pattern=r'^[^\x00-\x1F\x7F]+$'` regex constraint to all relevant string fields in Pydantic schemas (excluding multiline fields like markdown bodies or layout JSON).
