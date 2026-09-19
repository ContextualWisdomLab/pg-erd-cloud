## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2025-02-18 - Further Pydantic String Fields Validation Hardening
**Vulnerability:** Additional user-provided string fields in Pydantic models (`DiagramViewCreateIn.name`, `TableAnnotationUpsertIn.schema_name`, `TableAnnotationUpsertIn.relation_name`, `ApiKeyCreateIn.key_name`) were vulnerable to control character injections.
**Learning:** Missed fields during initial sanitization expose the application to terminal escape sequences or log injection.
**Prevention:** Apply `pattern=r'^[^\x00-\x1F\x7F]+$'` systematically across all relevant Pydantic string metadata fields.
