## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2025-02-18 - Hardening Multiple Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (`DiagramViewCreateIn.name`, `TableAnnotationUpsertIn.schema_name`, `TableAnnotationUpsertIn.relation_name`, `ApiKeyCreateIn.key_name`) were missing validation against control characters.
**Learning:** These fields are often logged, stored, or rendered, and missing strict pattern validation could lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection. Pydantic's `min_length`/`max_length` are not enough on their own.
**Prevention:** Always use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields that are not expected to hold newlines or other control characters.
