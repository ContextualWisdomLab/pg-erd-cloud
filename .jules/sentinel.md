## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2025-02-18 - JWT crit 헤더 검증 강제
**Vulnerability:** JWT `crit` (critical) 헤더가 존재할 때, RFC 7515에 따라 이를 명시적으로 검증하지 않으면 인지하지 못하는 중요 확장이 포함된 토큰을 허용하게 되어 보안 스캔(STRIX)을 통과하지 못합니다.
**Learning:** `PyJWT`나 `python-jose`를 사용할 때 `crit` 헤더의 타입 및 길이를 엄격히 검증(길이 제한 리스트 형태)해야 하고, 알 수 없는 확장에 대해서는 반드시 토큰을 거부해야 합니다.
**Prevention:** `_validate_jwt_header` 함수에서 `crit` 헤더 존재 여부를 확인하고, 길이가 제한된 문자열 리스트인지 확인하며, 지원하지 않는 확장(현재 0개)이 있으면 즉시 401을 반환하도록 수정합니다.
## 2026-08-23 - JWT Token Validation Error Message Leakage Fix
**Vulnerability:** The API returned highly specific error messages (e.g., "unknown signing key", "algorithm/key type mismatch", "unsupported token algorithm") during JWT validation, leaking internal implementation details to potential attackers.
**Learning:** Returning specific token validation errors allows attackers to perform reconnaissance on the auth mechanism, testing different vectors to map out the exact token requirements and libraries in use.
**Prevention:** Standardize all token validation failure responses to return a generic HTTP 401 with `detail="invalid token"` to provide no useful feedback to unauthorized requests.
