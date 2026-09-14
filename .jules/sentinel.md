## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2026-09-14 - Migrate from python-jose to PyJWT
**Vulnerability:** The backend depended on `python-jose` which pulled in `ecdsa`, exposing the application to Minerva timing attacks on P-256 (PYSEC-2026-1325 / GHSA-wj6h-64fc-37mp).
**Learning:** `python-jose` has unmaintained dependencies causing security alerts. `PyJWT` is an actively maintained alternative.
**Prevention:** Removed `python-jose` and its typing stubs from `pyproject.toml`, migrating JWT operations and PyJWK mocking to `PyJWT`.
