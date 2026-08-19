## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2024-05-18 - [JWT crit 파라미터 검증 누락]
**Vulnerability:** JWT `crit` (Critical) 헤더가 제공될 경우, 이를 명시적으로 검증하지 않으면 알 수 없는 위험한 파라미터가 실행되거나 보안 통제가 우회될 수 있는 취약점(RFC 7515 위반)이 발견되었습니다.
**Learning:** PyJWT와 같은 라이브러리를 사용할 때는 STRIX 보안 요구 사항에 맞게 JWT 헤더의 모든 필드를 명시적으로 검증해야 하며, 특히 `crit` 필드의 리스트 타입 확인 및 길이 제한을 구현해야 합니다.
**Prevention:** 인증 관련 코드를 작성할 때는 `crit` 배열의 모든 요소가 서버에서 지원하는 파라미터인지 검사하고, 지원하지 않는 경우 예외를 발생시키도록 설계해야 합니다.
