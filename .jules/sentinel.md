## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2023-10-25 - Prevent Information Leakage in JWT Validation
**Vulnerability:** JWT validation failures previously returned specific error messages (e.g., "token missing exp", "unsupported token type", "unknown signing key") which could provide an attacker with insight into the validation process and token structure.
**Learning:** To prevent information leakage during authentication, error responses must be genericized so that any validation failure returns the same non-descriptive message, ensuring attackers cannot deduce which part of the token validation failed.
**Prevention:** Ensure all JWT validation errors raise a generic HTTP 401 exception with `detail="invalid token"` rather than specifying the exact validation failure.
