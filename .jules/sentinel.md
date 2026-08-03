## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2026-08-01 - Hardening Unprotected Pydantic String Fields Against Control Characters
**Vulnerability:** Several Pydantic string fields (`DiagramViewCreateIn.name`, `TableAnnotationUpsertIn.schema_name`, `TableAnnotationUpsertIn.relation_name`, `ApiKeyCreateIn.key_name`) were missing the `pattern` parameter to restrict ASCII control characters.
**Learning:** Even when some fields have validation, developers often miss applying the same rigorous rules to new schemas. If a field lacks strict regex filtering (e.g., `pattern=r"^[^\x00-\x1F\x7F]+$"`), attackers can inject newlines, carriage returns, or terminal escapes which can lead to log forging or unexpected parsing errors down the line.
**Prevention:** Systematically apply `pattern=r"^[^\x00-\x1F\x7F]+$"` to all new identifier or name-based string fields in `backend/app/schemas.py`.
