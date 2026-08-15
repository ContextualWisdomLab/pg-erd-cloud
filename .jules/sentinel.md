## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2024-05-24 - Schema validation for SQL
**Vulnerability:** Missing explicit bounds check on the `sql` field in `ApplySqlIn` schema allowed terminal control characters.
**Learning:** Automated scanners flag this as an injection vulnerability. API boundaries must explicitly validate input schema bounds to satisfy automated scanners.
**Prevention:** Apply explicit regex validation (`pattern=r"^[^\x00-\x08\x0B\x0C\x0E-\x1F\x7F]+$"`) directly at the schema model layer to safely allow whitespace controls while blocking dangerous terminal escapes.
