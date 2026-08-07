## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2026-08-04 - Replace vulnerable python-jose with PyJWT
**Vulnerability:** The `python-jose` library is unmaintained and strictly pins dependencies to vulnerable versions of `ecdsa` (causing PYSEC-2026-1325).
**Learning:** `PyJWT` is the maintained alternative, but its API differs from `python-jose`. Specifically, `jwt.decode` requires a key object (e.g., `jwt.PyJWK(jwk).key`) rather than a raw dictionary, and its exceptions inherit from `jwt.PyJWTError` rather than `jose.JWTError`.
**Prevention:** Avoid adding unmaintained cryptographic libraries. When migrating libraries, thoroughly review and mock their specific object dependencies (like `PyJWK`) and exception hierarchies to prevent functional regressions like crashes on invalid inputs.
## 2026-08-07 - Incomplete JWT Validation (Missing `crit` checking)
**Vulnerability:** JWT `_decode_verified_oidc_token` logic didn't validate the `crit` (critical) header as per RFC 7515. This type-confusion vulnerability could be used to pass arbitrary header types, exhaust server resources via long strings/arrays, and bypass security controls.
**Learning:** Even well-known decoding libraries like `PyJWT` do not completely automate all business-logic checking required by RFCs. The specific check for unhandled `crit` arguments (and ensuring they are correctly typed and length-bounded) must be done explicitly to prevent attacks.
**Prevention:** Validate the `crit` header array immediately after obtaining unverified JWT headers, ensuring elements are strictly strings bounded in length.
