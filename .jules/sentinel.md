## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-02-18 - Enforcing `crit` Header Validation in JWT Verification
**Vulnerability:** The application did not explicitly validate the `crit` (critical) header parameter during JWT verification, silently ignoring unsupported critical extensions in tokens.
**Learning:** According to RFC 7515, if a token includes the `crit` header, it must be validated as a length-bounded list of strings, and the token must be rejected if the application does not support any of the included parameters. Failing to do so can lead to security bypasses or STRIX security scan alerts.
**Prevention:** Always validate the `crit` header in JWT JOSE headers. It must be checked as a list of strings, and if the application doesn't support critical parameters, any non-empty `crit` list should cause verification failure.
