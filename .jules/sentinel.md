## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2026-08-21 - JWT crit 헤더 검증 강화 (JWT Critical Extension Bypass 방지)
**Vulnerability:** JWT 파싱 중 `crit` (critical) 헤더가 있을 경우 이를 엄격히 검증하여 거부하는 로직이 없어 RFC 7515 표준을 위반하고, 잠재적으로 공격자가 지원되지 않는 중요 확장을 강제할 수 있는 보안 취약점이 있었습니다.
**Learning:** `crit` 헤더는 토큰 처리자가 반드시 이해하고 처리해야 하는 확장 파라미터의 목록을 명시합니다. 이를 무시하면 서명 검증을 우회하거나 예기치 않은 토큰 처리가 발생할 수 있다는 점을 배웠습니다.
**Prevention:** JOSE 헤더 검증 로직(`_validate_jwt_header`)에 `crit` 파라미터 존재 여부를 명시적으로 확인하고, 존재할 경우 엄격한 타입 검사를 수행한 뒤 모두 지원되지 않는 것으로 간주하여 `401 Unauthorized`를 반환하도록 수정해야 합니다.
