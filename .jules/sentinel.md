## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters (C0 and C1)
**Vulnerability:** User-provided string fields lacked validation against the C1 control characters (U+0080–U+009F), leaving them vulnerable to extended control character injection in addition to standard C0 characters.
**Learning:** Initial validation only blocked `\x00-\x1F` and `\x7F` but left the C1 range open. It's critical to reject all control characters, including `\x80-\x9F` for defense in depth. Python `\x80-\x9F` string literals need careful formatting in raw strings or encoded replacements to avoid `SyntaxError: source code string cannot contain null bytes` issues.
**Prevention:** Use explicit regex validation `pattern=r"^[^\x00-\x1F\x7F\x80-\x9F]+$"` on Pydantic string fields to strictly reject all control characters (C0 and C1) while allowing printable text.
