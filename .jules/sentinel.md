## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-05-18 - Fix Terminal Escape / Log Injection (C1 Controls)
**Vulnerability:** Pydantic regex fields only rejected C0 control characters (`\x00-\x1F\x7F`), allowing C1 control characters (`\x80-\x9F`) which could bypass string sanitization and cause terminal escape injections or log injection on some systems.
**Learning:** Python source parsing strictly throws SyntaxErrors if literal null bytes are written into strings. Patch scripts replacing raw strings must be extremely careful to avoid hex evaluation by using plain string replacements of explicitly escaped strings instead of complex `re.sub` or `chr(0)`.
**Prevention:** Construct regex replacements safely in patches avoiding raw byte evaluations, and always validate regex patterns for full control character coverage (both C0 and C1) in API schemas.
