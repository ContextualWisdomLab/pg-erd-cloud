## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2026-08-05 - Replace python-jose with PyJWT
**Vulnerability:** The `python-jose` library is unmaintained and pins to a vulnerable version of `ecdsa` causing PYSEC-2026-1325.
**Learning:** Legacy JOSE libraries can fall behind security standards and pin vulnerable dependencies, affecting overall backend security.
**Prevention:** Rely on well-maintained JWT libraries like `PyJWT[crypto]` and actively monitor dependency CVEs.
