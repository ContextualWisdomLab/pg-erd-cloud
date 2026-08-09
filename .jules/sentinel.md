## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-02-27 - Strict ASCII Control Character Validation in Pydantic Schemas
**Vulnerability:** Pydantic `str` fields intended for identifiers/names (e.g., `DiagramViewCreateIn.name`, `TableAnnotationUpsertIn.schema_name`, `ApiKeyCreateIn.key_name`) were previously lacking strict validation against ASCII control characters, exposing the system to potential log injection and terminal escape sequence vulnerabilities.
**Learning:** Standard length limits (`min_length`, `max_length`) do not prevent the ingestion of invisible control characters (`\x00-\x1F\x7F`).
**Prevention:** Enforce strict pattern matching using `pattern=r"^[^\x00-\x1F\x7F]+$"` for string fields that do not legitimately require multiline inputs or control characters, preventing malicious inputs from persisting into logs or execution environments.
