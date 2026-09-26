## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2024-05-24 - [보안 개선] 인증 예외 메시지 통합
**Vulnerability:** 인증 실패 시 상세한 예외 메시지(예: 알고리즘 불일치, 서명 키 오류, 클레임 누락 등)가 클라이언트에 노출되어 잠재적으로 토큰 검증 로직이나 설정 등의 민감한 정보가 유출될 위험이 존재함.
**Learning:** 예외 처리 시 구체적인 오류 내용을 상세히 반환하는 것은 디버깅에 유리할 수 있으나, 공격자에게 유용한 정보를 제공하여 시스템의 구조나 상태를 추측하게 할 수 있음. 디버깅 편의성을 위해 구체적인 실패 원인은 서버의 로그로만 남겨야 함.
**Prevention:** 모든 토큰 인증 관련 401 오류 메시지를 "invalid token"과 단일 메시지로 통일하여(Generic Error Messages) 상세한 오류 원인을 클라이언트에 노출하지 않도록 한다. 동시에, 원본 오류 내용은 서버에 `logger.warning()`으로 기록하여 운영자의 디버깅을 돕는다.
