## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2026-08-04 - SSRF 방지 및 XSS 완화
**Vulnerability:**
1. **Critical - SSRF via Database Connection DSN (CVE-918):** `isSupportedConnectionDsn()` 함수에서 프로토콜과 호스트명 존재 여부만 확인하여, 악의적인 사용자가 클라우드 메타데이터 엔드포인트(169.254.169.254, metadata.google.internal)나 프라이빗 IP 범위(10.0.0.0/8 등), 로컬호스트를 입력해 백엔드가 내부망으로 요청을 보내도록 유도할 수 있었습니다.
2. **Medium - Inconsistent XSS Protection (CWE-79):** 사용자 제어 데이터인 `project_name`이 일부 UI(프로젝트 선택 드롭다운, 사이드바 요약, 다이어그램 헤더)에서 `sanitizeHtml()`을 거치지 않고 직접 렌더링되었습니다. (React의 기본 escaping이 적용되더라도, 프로젝트의 명시적인 일관성 유지 원칙에 어긋남).

**Learning:**
- 클라이언트 측에서 URL을 파싱할 때 `new URL(value)`의 `hostname` 속성을 검증하여 내부 IP 대역 및 예약된 호스트명을 명시적으로 차단함으로써 Defense-in-depth(심층 방어)를 구현해야 합니다.
- 비록 React 환경이더라도 `dangerouslySetInnerHTML` 또는 외부 출력용 포맷과 연계될 가능성이 있는 일관된 XSS 방어를 위해 기존 `sanitizeHtml()`을 모든 텍스트 보간에 통일성 있게 적용해야 합니다.

**Prevention:**
- DSN 유효성 검사 로직에 정규식을 통한 RFC 1918 프라이빗 네트워크 및 클라우드 메타데이터 IP 대역, IPv6 루프백 등을 필터링하는 화이트/블랙리스트 기반 검증을 추가했습니다.
- 모든 누락된 `project_name` 렌더링 지점에 `sanitizeHtml()` 래퍼를 적용하여 데이터의 안전성을 보장했습니다.

## 2026-08-04 - undici 패키지 취약점 조치
**Vulnerability:**
- **High/Medium - Undici vulnerabilities (CVE-2026-13697, CVE-2026-16728, CVE-2026-14643, CVE-2026-15157, CVE-2026-16729):** `jsdom` 의존성을 통해 설치된 `undici` 패키지 버전에 다수의 보안 취약점 (CRLF 인젝션, 정보 노출, 응답 역동기화 등)이 존재했습니다.

**Learning:**
- `package-lock.json` 상의 하위 의존성(transitive dependencies)이라도 높은 위험도의 취약점이 포함되어 있다면 OSV-scanner 등 보안 점검 도구를 통해 감지되므로, 최상위 `package.json`에서 의존성을 추가하거나 업데이트하여 해결해야 합니다.

**Prevention:**
- `undici` 버전을 7.29.0 이상으로 명시적으로 업데이트하여 취약점을 해결했습니다.
