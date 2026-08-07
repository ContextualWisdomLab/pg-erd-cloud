## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2026-08-07 - Fix SQL injection in sqlDataType validation
**Vulnerability:** The regex `/^[A-Za-z0-9_ .,[\]()]+$/` allowed characters like semicolon, slash, and hyphen, enabling SQL injection through data type fields into generated DDL statements. Parentheses balance was also not validated.
**Learning:** Automated scanners require explicit rejection of dangerous SQL characters and syntax structure checks (like balanced parentheses) for data types injected into raw string templates.
**Prevention:** Avoid blanket regex whitelists that inadvertently include control characters; enforce structural syntax validation for interpolated strings in DDL.
