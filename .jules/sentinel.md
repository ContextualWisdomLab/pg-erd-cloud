## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-02-18 - Replacing python-jose with PyJWT for Dependency Vulnerability Remediation
**Vulnerability:** The `python-jose` library contains an older, insecure implementation dependency on `ecdsa` (specifically triggering the Minerva timing attack on P-256 in `python-ecdsa` CVE-2024-23342, PYSEC-2026-1325).
**Learning:** `python-jose` brings in vulnerable legacy dependencies (like `ecdsa<=0.19.2`). `PyJWT` provides modern, secure JWT handling without relying on outdated sub-dependencies.
**Prevention:** Always use `PyJWT` for JWT operations and strictly configure it (e.g., `algorithms=...`, `options={"require_...": True}`) since its validation syntax differs from `python-jose`. Avoid `python-jose` in new projects due to dependency staleness.
