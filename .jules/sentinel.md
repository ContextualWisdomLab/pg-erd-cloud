## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2024-08-16 - JWT crit header validation
**Vulnerability:** 애플리케이션에 JWT JOSE 헤더의 `crit` (critical) 매개변수에 대한 검증이 누락되어 있었습니다. 공격자가 인식할 수 없는 critical 매개변수를 포함한 JWT를 전송할 경우, RFC 7515에 따라 토큰을 엄격하게 거부해야 함에도 불구하고 애플리케이션이 이를 잘못 처리할 위험이 있었습니다.
**Learning:** 애플리케이션이 어떠한 critical 확장(extension)을 지원하지 않더라도, RFC 7515는 `crit` 헤더가 존재할 경우 반드시 문자열 리스트로 검증되어야 하며 인식할 수 없는 매개변수가 하나라도 포함된 토큰은 거부되어야 한다고 명시합니다. 이를 위반하면 STRIX 보안 검사를 통과하지 못할 뿐만 아니라 예상치 못한 동작이 발생할 수 있습니다.
**Prevention:** 애플리케이션이 사용하는 JOSE 헤더만 검증하고, 잘못되었거나 지원되지 않는 `crit` 선언은 명시적으로 거부해야 합니다. 인식하지 못한 비-critical JOSE 헤더 전체를 거부하는 정책으로 확대해 기록하지 않습니다.
