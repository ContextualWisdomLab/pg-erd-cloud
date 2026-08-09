## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2024-05-24 - JWT Header Verification Missing `crit` Processing
**Vulnerability:** OIDC 토큰 검증 시, JWT 헤더의 `crit` (critical) 필드가 확인되지 않고 무시되고 있었습니다.
**Learning:** RFC 7515에 따르면 `crit` 헤더는 배열 형태여야 하며, 명시된 확장 파라미터들을 서버가 이해하고 처리할 수 있어야만 토큰을 수용해야 합니다. 이를 확인하지 않으면 STRIX 보안 요건을 통과할 수 없고 알 수 없는 확장 기능이 포함된 토큰이 악용될 위험이 있습니다. 이 프로젝트의 경우 커스텀 확장을 지원하지 않으므로 `crit` 헤더가 포함된 토큰은 거부되어야 합니다.
**Prevention:** `_validate_jwt_header` 함수에 `crit` 파라미터가 있는지 검사하는 로직을 추가하고, 만약 존재할 경우 문자열의 배열(길이 10 이하)인지 확인 후 지원되지 않는 확장 기능이므로 예외를 발생시키도록 수정했습니다.
