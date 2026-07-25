## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-02-18 - Robust DSN Redaction against urllib.parse idiosyncrasies
**Vulnerability:** DSNs with non-standard schemes containing underscores (e.g., `snowflake_invalid://`) or missing slashes (e.g., `scheme:user:password@host/db`) caused `urlsplit` to fail to parse the `netloc` and `password`, bypassing credential redaction when error messages were returned to the user.
**Learning:** `urllib.parse` evaluates schemes with underscores to an empty scheme, and places authorities into the `path` when `://` is missing, bypassing standard extraction.
**Prevention:** Temporarily substitute non-standard/invalid schemes with a valid dummy scheme (e.g. `http`) and fallback to splitting on `:` when `netloc` is empty to force `urlsplit` to correctly parse and extract secrets.

## 2025-02-18 - Replacing Unmaintained python-jose library
**Vulnerability:** Dependency review identified a high severity vulnerability `Minerva timing attack on P-256 in python-ecdsa` (GHSA-wj6h-64fc-37mp / PYSEC-2026-1325) introduced via the unmaintained `python-jose` library which relies on vulnerable `ecdsa` < 0.19.0 version limits.
**Learning:** `python-jose` strictly pins its dependencies and hasn't been updated for years, making it dangerous.
**Prevention:** Replace `python-jose` with `PyJWT` for JWT decoding to allow secure cryptography components and eliminate the dependency on outdated ecdsa versions.
