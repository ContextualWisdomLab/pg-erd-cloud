## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2024-05-24 - JWT 에러 메시지 정보 유출 취약점 수정
**Vulnerability:** JWT 검증 과정에서 구체적인 예외 메시지("token missing exp", "unsupported token algorithm", "algorithm/key type mismatch" 등)를 반환하여 내부 검증 로직이 외부에 노출될 수 있음.
**Learning:** 애플리케이션의 인증 실패 응답은 구체적인 실패 원인을 알려주면 공격자에게 공격 표면(예: 서명 키, 토큰 지원 알고리즘, 만료 여부 등)을 파악할 수 있는 단서가 됨을 알 수 있었음.
**Prevention:** 모든 토큰 검증 오류 상황에 대해 일관되게 "invalid token"과 같은 일반적인 메시지를 반환하도록 변경하여 공격자가 내부 검증 로직을 추론할 수 없도록 방어해야 함.
