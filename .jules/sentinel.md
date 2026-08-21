## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2026-08-16 - [Frontend nanoid 무한 루프 취약점 해결]
**Vulnerability:** nanoid 3.3.16 및 이전 버전에서 크기 매개변수가 0인 커스텀 생성기를 사용할 때 무한 루프에 빠져 CPU를 고갈시키고 Denial of Service를 유발하는 취약점이 발견되었습니다.
**Learning:** 애플리케이션에서 직접 사용하지 않더라도 프론트엔드 환경의 빌드/개발 의존성 또는 간접 의존성에 포함된 패키지가 특정 매개변수로 호출되면 DoS를 유발할 수 있습니다.
**Prevention:** `nanoid` 버전을 안전한 `3.3.18` 이상으로 오버라이드 및 고정하도록 `package.json`에서 `overrides`를 사용하고 패키지를 업데이트하여 수정했습니다.
