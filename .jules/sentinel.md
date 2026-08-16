## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2026-08-15 - Case-Sensitive Prisma Reserved Words Bypass
**Vulnerability:** The Prisma schema export functionality (`sanitizeName`) lacked validation against Prisma reserved keywords ("datasource", "generator", "model", "enum"). Furthermore, checking reserved keywords without standardizing case allows inputs like "Model" or "DATA_SOURCE" to bypass validation, potentially resulting in corrupted generated Prisma schema files.
**Learning:** Security validations on user-provided schema names must be case-insensitive to ensure reliable input sanitization and prevent simple casing bypasses.
**Prevention:** Normalize user-provided input strings (e.g. `toLowerCase()`) prior to validating them against lists of reserved keywords.
