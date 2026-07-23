## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation that blocks C0/C1 control ranges (for example `r'^[^\x00-\x1F\x7F-\x9F]+$'`) with a Pydantic v2-friendly API such as `Field(pattern=...)` or `StringConstraints(pattern=...)`.
