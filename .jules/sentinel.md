## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2025-02-28 - Missing Control Character Validation in String Inputs
**Vulnerability:** Missing control character validation (e.g., against terminal escape injections and log injections) in several string fields in Pydantic schemas (`DiagramViewCreateIn.name`, `TableAnnotationUpsertIn.schema_name`, `TableAnnotationUpsertIn.relation_name`, `ApiKeyCreateIn.key_name`).
**Learning:** Even though basic length limits are set via `min_length` and `max_length`, user-supplied strings can still carry hidden control characters like ANSI escape sequences, causing terminal/log injections when accessed or presented. This codebase requires explicit protection against control characters in string fields using the pattern `pattern=r"^[^\x00-\x1F\x7F]+$"`.
**Prevention:** For any user-provided string fields in Pydantic schemas that are stored or displayed, always add an explicit regex pattern `pattern=r"^[^\x00-\x1F\x7F]+$"` to filter out control characters.
