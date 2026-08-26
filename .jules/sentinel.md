## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-02-27 - JWT 검증 시 Critical (crit) 헤더 필수 검증 및 에러 메시지 정보 노출 방지
**Vulnerability:** JWT 파싱 중 `crit` 헤더를 검증하지 않아 RFC 7515 요구사항과 STRIX 보안 점검을 우회할 수 있었고, JWT 검증 실패 시 자세한 에러 메시지가 반환되어 정보가 유출될 위험이 존재했습니다.
**Learning:** `crit` 헤더는 안전하게 길이와 내용이 제한된 문자열 리스트로 검증되어야 하며, 인가 실패 시 공격자에게 너무 자세한 검증 실패 사유(예: "token missing exp" 등)를 노출해서는 안 됩니다.
**Prevention:** `_validate_jwt_header`에서 `crit` 배열의 존재와 형태를 엄격하게 검증하고, 모든 JWT 예외 처리에서 자세한 사유 대신 HTTP 401 `"invalid token"`을 반환하여 내부 검증 로직 노출을 차단합니다.
