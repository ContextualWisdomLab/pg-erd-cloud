## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2026-09-09 - [Control Character Injection via Pydantic String Fields]
**Vulnerability:** String fields in Pydantic schemas (e.g., `DiagramViewCreateIn.name`, `TableAnnotationUpsertIn.schema_name`, etc.) lacked explicit character restrictions, allowing control characters (like `\x00-\x1F` and `\x7F`) to be injected through the API.
**Learning:** While these fields don't directly execute code, control characters can cause log injection, terminal escape vulnerabilities, or downstream processing issues in PostgreSQL. It is a defense-in-depth practice to restrict these fields if they aren't explicitly multiline.
**Prevention:** Use explicit regex pattern `pattern=r"^[^\x00-\x1F\x7F]+$"` for Pydantic string fields that do not legitimately require multiline inputs or complex formatting.
