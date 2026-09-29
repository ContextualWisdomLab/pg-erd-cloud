## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-02-18 - JWT crit 헤더 검증 강화
**Vulnerability:** JWT 검증 과정에서 `crit` (critical) 헤더가 제공되었을 때 이를 명시적으로 검증하고 인지하지 못하는 매개변수를 거부하는 로직이 누락되어 RFC 7515를 위반하고 보안 스캔(STRIX)을 통과하지 못했습니다.
**Learning:** `crit` 헤더가 존재할 경우, 이는 반드시 문자열의 리스트여야 하며 인식되지 않는 매개변수가 하나라도 포함되어 있다면 토큰을 즉시 거부(HTTP 401)해야 함을 인지했습니다. 이를 통해 악의적인 JWT 확장 기능을 무시하여 발생하는 잠재적 취약점을 방지할 수 있습니다.
**Prevention:** JWT 헤더 검증 로직에 `crit` 속성이 포함되어 있는지 확인하고, 존재할 경우 길이 제한이 있는 문자열 리스트로 파싱한 후 인식되지 않는 확장에 대해 엄격하게 `invalid token header` 예외를 발생시키도록 합니다.
