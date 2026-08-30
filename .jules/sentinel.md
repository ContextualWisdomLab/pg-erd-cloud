## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2025-05-24 - Fix Log and Terminal Escape Injection in Schemas
**Vulnerability:** Missing control character validation in Pydantic schema inputs (`DiagramViewCreateIn.name`, `TableAnnotationUpsertIn.schema_name`, `TableAnnotationUpsertIn.relation_name`, `ApiKeyCreateIn.key_name`).
**Learning:** Even internal API inputs need strict validation. Unsanitized strings could allow log injection or terminal escape sequence injection if these values are printed or logged in administrative views or CI environments.
**Prevention:** Apply explicit regex validation `pattern=r"^[^\x00-\x1F\x7F]+$"` for all Pydantic string fields that accept user input to ensure no control characters are stored or processed.
