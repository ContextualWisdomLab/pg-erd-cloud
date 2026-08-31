## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2025-02-18 - Generic JWT Validation Error Messages
**Vulnerability:** JWT validation failures (such as missing claims, mismatched algorithm/key types, or unsupported token types) were exposing specific error details like `"token missing jti"` or `"unsupported token type"` in API responses.
**Learning:** This information leakage can help attackers incrementally learn the system's JWT validation rules, allowing them to iterate and craft attacks more effectively (e.g. knowing exactly which claim they missed).
**Prevention:** Always raise a generic `401 Unauthorized` exception with a uniform message like `detail="invalid token"` for all token validation failures to prevent side-channel information leakage.
