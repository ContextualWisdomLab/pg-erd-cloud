## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2024-10-09 - [Fix control character injection in string fields]
**Vulnerability:** Control characters could be injected in Pydantic schema string fields (`DiagramViewCreateIn.name`, `TableAnnotationUpsertIn.schema_name`, `TableAnnotationUpsertIn.relation_name`, `ApiKeyCreateIn.key_name`).
**Learning:** Pydantic `Field` without a proper regex pattern validation allows control characters by default, leading to log injection and terminal escape sequence vulnerabilities. Multiline fields (like `body`) need to permit formatting characters, but names and keys should not.
**Prevention:** Apply `pattern=r"^[^\x00-\x1F\x7F]+$"` for user-provided single-line string fields in Pydantic schemas.
