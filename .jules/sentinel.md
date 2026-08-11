## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2026-08-11 - JWT Header `crit` Verification
**Vulnerability:** JWT `crit` (critical) headers were not validated, violating RFC 7515. An attacker could potentially bypass security controls by including unsupported critical extensions that the application silently ignored.
**Learning:** In any JOSE/JWT implementation, the `crit` header must be explicitly verified. If present, it must be a list of strings, and all items in the list must be understood by the application. If the application doesn't support custom extensions, it should reject any token carrying a `crit` header.
**Prevention:** Always validate the `crit` header explicitly during JWT decoding or pre-decoding. Reject explicit `null`, empty or oversized arrays, non-string members, and every extension the application does not support.
