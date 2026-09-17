## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2023-10-27 - Hardening JWT Validation Configuration
**Vulnerability:** The `jose` (python-jose) package is abandoned and contains unresolved vulnerabilities (e.g., related to ecdsa dependencies). Furthermore, PyJWT requires a different API configuration; specifically, using individual boolean flags like `require_iss` inside the `options` dict raises a `ValueError` because it only accepts a `require` list.
**Learning:** PyJWT requires creating a valid cryptographic key object using `jwt.PyJWK.from_dict(jwk).key` rather than a raw dictionary. Additionally, mocked JWKs in tests must include structural attributes like `n` and `e` for successful PyJWK instantiation.
**Prevention:** Always follow PyJWT's API documentation directly. When swapping out unmaintained security packages like python-jose, thoroughly test mock data as internal parsers generally demand stricter structural compliance.
