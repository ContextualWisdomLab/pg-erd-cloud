## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-02-23 - Hardening Pydantic String Fields Against Control Characters (Part 2)
**Vulnerability:** Additional user-provided string fields (`DiagramViewCreateIn.name`, `TableAnnotationUpsertIn.schema_name`, `TableAnnotationUpsertIn.relation_name`, `ApiKeyCreateIn.key_name`) lacked strict validation against control characters.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly. Furthermore, adding explicit `# SECURITY: ...` comments alongside the validation helps future developers understand the necessity of the regex pattern.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on all Pydantic string fields to strictly reject control characters, and document the reason with inline security comments.
