## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-02-18 - Enforcing `crit` Header Validation in JWT Verification
**Vulnerability:** The application did not explicitly validate the `crit` (critical) header parameter during JWT verification, silently ignoring unsupported critical extensions in tokens.
**Learning:** According to RFC 7515, if a token includes the `crit` header, it must be validated as a length-bounded list of strings, and the token must be rejected if the application does not support any of the included parameters. Failing to do so can lead to security bypasses or STRIX security scan alerts.
**Prevention:** Always validate the `crit` header in JWT JOSE headers. It must be checked as a list of strings, and if the application doesn't support critical parameters, any non-empty `crit` list should cause verification failure.

## 2025-02-18 - Fix Force Refresh Bypass Vulnerability in JWT JWKS Refresh
**Vulnerability:** A logical error in `_get_jwks` overrode the `force_refresh` parameter. Redundant caching logic allowed cached keys to be returned even when `force_refresh=True` was explicitly requested.
**Learning:** This flaw could potentially cause denial of service during key rotation or let attackers abuse timed windows to have illegitimate tokens accepted.
**Prevention:** Ensure caching and short-circuit conditions clearly distinguish between default logic and explicit override flags (like `force_refresh`).

## 2025-02-18 - Replacing Unmaintained `python-jose` with `PyJWT[crypto]`
**Vulnerability:** The application was using the `python-jose` library, which is unmaintained and pins its dependencies to vulnerable versions of `ecdsa` (causing PYSEC-2026-1325). This vulnerability allows a Minerva timing attack on P-256 in python-ecdsa.
**Learning:** Using unmaintained cryptography libraries exposes the application to supply-chain vulnerabilities, as they block security updates in their transitive dependencies.
**Prevention:** Replace `python-jose` with the actively maintained `PyJWT[crypto]` library for JWT handling in the backend. Ensure tests and code are updated to use the new `jwt` module properly.
