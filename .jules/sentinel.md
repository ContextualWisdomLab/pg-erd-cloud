## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2024-05-18 - JWT crit 헤더 검증 누락 수정
**Vulnerability:** JWT `crit` (critical) 헤더가 존재할 때 이를 검증하고 인식하지 못하는 파라미터가 포함되어 있으면 거부해야 하는 RFC 7515 표준을 준수하지 않음.
**Learning:** PyJWT는 자체적으로 `crit` 헤더를 엄격하게 검증하지만, 이를 위해 적절히 인자를 전달하지 않으면 STRIX 보안 검사에서 취약점으로 보고될 수 있음. 또한 명시적으로 허용하지 않는 `crit` 확장을 모두 거부하는 방어적인 코드를 작성하는 것이 안전함.
**Prevention:** JWT 헤더를 수동으로 검증할 때 `crit` 헤더가 존재한다면 길이 제한이 있는 문자열 리스트인지 확인하고, 지원하지 않는 확장 파라미터가 있다면 즉시 401 에러를 발생시켜야 함.
