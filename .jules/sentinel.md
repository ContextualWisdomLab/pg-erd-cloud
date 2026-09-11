## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2025-02-14 - JWT Header "crit" parameter validation
**Vulnerability:** Missing explicit validation for the JWT header `crit` (critical) parameter as per RFC 7515. Information leakage during token validation errors.
**Learning:** STRIX security scans expect exact enforcement of the `crit` header handling (length bounds, explicit checks, type validation). Also, detailed 401 response messages for JWT failures leak information about validation procedures and why tokens failed, creating potential probing targets.
**Prevention:** Always validate the `crit` parameter if present, verifying its list properties and elements. Consolidate token validation 401 errors to a generic "invalid token" detail string to avoid leaking auth setup details.
