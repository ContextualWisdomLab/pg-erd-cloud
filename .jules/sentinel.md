## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2026-09-11 - Pydantic Field Validation Exception for Database Identifiers
**Vulnerability:** Adding strict control character filtering (`^[^\x00-\x1F\x7F]+$`) indiscriminately broke legitimate functionality involving PostgreSQL source identifiers.
**Learning:** Certain database identifiers (like `schema_name` and `relation_name`) validly preserve non-null control characters in PostgreSQL. Banning them unconditionally breaks compatibility.
**Prevention:** For fields representing database objects, use `pattern=r"^[^\x00]+$"` to only ban the null byte (`\x00`), which is structurally invalid, while preserving the full range of valid identifiers. Keep the strict `r"^[^\x00-\x1F\x7F]+$"` pattern only for product-owned generic strings (e.g. `ApiKeyCreateIn.key_name` or `DiagramViewCreateIn.name`).
