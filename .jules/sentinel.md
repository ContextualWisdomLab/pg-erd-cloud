## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-02-18 - Prevent Information Leakage in JWT Validation
**Vulnerability:** The authentication endpoint leaked specific details about JWT validation failures (e.g., "token missing jti", "algorithm/key type mismatch") in 401 Unauthorized responses.
**Learning:** Returning overly verbose error messages can allow attackers to probe token states, enumerate revocation status, or reverse-engineer the underlying validation logic.
**Prevention:** Standardize 401 Unauthorized `HTTPException` detail messages during authentication to a generic `"invalid token"` while ensuring underlying exceptions are appropriately logged (e.g., using exception chaining `from err`) for server-side APM tools.
