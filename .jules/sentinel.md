## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2026-09-16 - Adding Security Comments for Control Character Injection Prevention
**Vulnerability:** Even when control character injection was mitigated with regex, the specific security purpose wasn't documented, making it susceptible to accidental removal by future developers unaware of the log injection risks.
**Learning:** Security controls without explicit documentation can be fragile and might be misinterpreted as generic length/format validations.
**Prevention:** Always pair security-critical regex patterns with an explicit inline comment explaining the vulnerability they prevent (e.g., ).

## 2026-09-17 - Migrate python-jose to PyJWT
**Vulnerability:** The `python-jose` package depends on a vulnerable version of `ecdsa` which allows a Minerva timing attack on P-256.
**Learning:** Relying on unmaintained crypto libraries like `python-jose` exposes the application to underlying dependency vulnerabilities that aren't patched upstream.
**Prevention:** Replace deprecated dependencies with actively maintained equivalents like `PyJWT`.
