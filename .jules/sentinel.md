## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2024-11-07 - Log Injection Prevention
**Vulnerability:** User-provided string fields in Pydantic models (like `ApiKeyCreateIn` and `DiagramViewCreateIn`) lacked explicit regex validation against control characters, exposing the system to log injection and terminal escape injection.
**Learning:** Multiline fields (like `dbml` or `body`) require whitespace characters (`\n`, `\r`, `\t`) and should not have strict regex applied to avoid functional regressions, but names and keys must be validated.
**Prevention:** Apply `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields that are not multiline to explicitly reject control characters.
