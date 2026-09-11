## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2025-02-18 - Avoid Information Leakage in JWT Validation
**Vulnerability:** JWT validation errors raised specific exceptions (e.g., "token missing sub", "algorithm/key type mismatch", "invalid token header") that leaked the exact reason for authentication failure.
**Learning:** Detailed validation error messages can provide attackers with insights into the authentication flow and configuration, potentially aiding in bypassing or forging tokens.
**Prevention:** Always raise a generic HTTP 401 exception with `detail="invalid token"` for all JWT validation errors to prevent information leakage.
