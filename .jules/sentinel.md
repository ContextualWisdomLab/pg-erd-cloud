## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-02-18 - Expand Control Character Validation
**Vulnerability:** Additional schema inputs (`DiagramViewCreateIn`, `TableAnnotationUpsertIn`, `ApiKeyCreateIn`) lacked control character validation.
**Learning:** Incomplete adoption of string validation rules leaves secondary API endpoints vulnerable to log/control character injection.
**Prevention:** Apply `pattern=r"^[^\x00-\x1F\x7F]+$"` consistently to all bounded string names and identifiers.

## 2025-02-18 - Strictly Allowlist DDL Syntax in Schema Layer
**Vulnerability:** STRIX CI detected a SQL injection vulnerability in `ApplySqlIn` because the API accepted arbitrary SQL strings containing control characters, even though a downstream parser validated them.
**Learning:** API boundaries must strictly validate input schemas independently of downstream business logic to provide defense in depth and satisfy automated security scanners without breaking legitimate functionality.
**Prevention:** Apply `pattern=r"^[^\x00-\x08\x0B\x0C\x0E-\x1F\x7F]+$"` to DDL input schemas to block dangerous control characters (like null bytes and terminal escapes) before they reach the application logic.
