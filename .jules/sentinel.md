## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2025-02-20 - Hardening Additional Pydantic String Fields Against Control Characters
**Vulnerability:** Several user-provided string fields (e.g., `DiagramViewCreateIn.name`, `ApiKeyCreateIn.key_name`, `TableAnnotationUpsertIn.schema_name`, and `TableAnnotationUpsertIn.relation_name`) lacked validation against control characters.
**Learning:** Inconsistent application of control character validation across schema fields leaves potential vectors for Log Injection (CRLF injection) or terminal escape sequence injection. It's crucial to ensure all relevant Pydantic string fields have a strict regex pattern.
**Prevention:** Apply the explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` consistently across all Pydantic string fields that do not legitimately require control characters.
