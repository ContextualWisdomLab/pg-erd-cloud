## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2024-05-18 - PyJWT 마이그레이션 보안 요구사항
**Vulnerability:** PyJWT 마이그레이션 중 JWT `crit` (critical) 헤더에 대한 불완전한 검증.
**Learning:** python-jose와 달리 PyJWT는 모든 RFC 7515 요구사항을 자동으로 검증하거나 강제하지 않습니다. `crit` 헤더는 길이가 제한된 문자열 리스트로 명시적으로 검증되어야 하며, 인식되지 않은 확장을 포함하는 토큰은 거부되어야 합니다.
**Prevention:** PyJWT로 JWT를 디코딩할 때 `crit` 헤더를 명시적으로 검증하여 보안 확장을 우회하는 것을 방지합니다.
