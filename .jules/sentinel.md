## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-02-18 - Hardening Remaining Pydantic String Fields Against Control Characters
**Vulnerability:** Several user-provided string fields (DiagramViewCreateIn.name, TableAnnotationUpsertIn.schema_name/relation_name, and ApiKeyCreateIn.key_name) lacked strict validation against control characters, relying only on length constraints.
**Learning:** Incomplete validation coverage leaves residual risks of Log Injection, Null Byte Injection, or payload corruption. A single previous fix didn't cover all vulnerable fields.
**Prevention:** Apply the explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` systematically to all applicable Pydantic string fields representing single-line names or identifiers.
