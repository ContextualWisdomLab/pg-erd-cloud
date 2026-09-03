## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2025-02-18 - Prevent Information Leakage During JWT Authentication
**Vulnerability:** JWT validation errors were exposing specific failure reasons (e.g., "unknown signing key", "token revoked", "algorithm/key type mismatch") in HTTP 401 response details.
**Learning:** Returning overly verbose authentication errors leaks internal state and validation logic, which attackers can use to probe or bypass the authentication mechanism.
**Prevention:** Always use generic error messages (e.g., "invalid token") for authentication failures, and ensure the test suite is configured to expect these generic responses to enforce this pattern.
