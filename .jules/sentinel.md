## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2026-10-01 - Replaced unmaintained python-jose with pyjwt
**Vulnerability:** `python-jose` depends on an outdated version of `ecdsa` containing the Minerva timing attack vulnerability on P-256 (CVE-2024-XXXX, high severity).
**Learning:** Legacy JWT libraries might lack updates and drag in vulnerable cryptographic dependencies. PyJWT expects `leeway` as a top-level kwarg rather than in `options`.
**Prevention:** Migrate to actively maintained libraries like `PyJWT` and regenerate lockfiles to purge transitive vulnerable dependencies.
