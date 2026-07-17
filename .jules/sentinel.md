## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-02-18 - [DSN 비밀번호 추출 우회 취약점 수정]
**Vulnerability:** 백엔드의 DSN 마스킹 로직이 `://`가 누락되거나 밑줄이 포함된 비표준 스키마를 사용하는 DSN에서 자격 증명을 추출하지 못해 에러 로그에 비밀번호가 노출되는 취약점이 있었습니다.
**Learning:** `urllib.parse.urlsplit`은 이러한 비표준 스키마를 파싱할 때 `netloc`을 채우지 못하고 자격 증명 부분을 `path`로 파싱합니다. 기존 대체 로직은 `://`가 포함된 DSN만 처리했습니다.
**Prevention:** `://`가 없을 때 `:`와 `@`가 있는 스키마를 올바르게 식별하도록 대체 파싱 로직을 개선하고, `urlsplit`이 정상적으로 토큰화할 수 있도록 더미 `http://` 스키마를 주입하여 해결했습니다.
