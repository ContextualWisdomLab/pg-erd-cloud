## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2026-08-21 - JWT crit 헤더 검증 강화 (JWT Critical Extension Bypass 방지)
**Vulnerability:** JWT 파싱 중 `crit` (critical) 헤더가 있을 경우 이를 엄격히 검증하여 거부하는 로직이 없어 RFC 7515 표준을 위반하고, 잠재적으로 공격자가 지원되지 않는 중요 확장을 강제할 수 있는 보안 취약점이 있었습니다.
**Learning:** `crit` 헤더는 토큰 처리자가 반드시 이해하고 처리해야 하는 확장 파라미터의 목록을 명시합니다. 이를 무시하면 서명 검증을 우회하거나 예기치 않은 토큰 처리가 발생할 수 있다는 점을 배웠습니다.
**Prevention:** JOSE 헤더 검증 로직(`_validate_jwt_header`)에 `crit` 파라미터 존재 여부를 명시적으로 확인하고, 존재할 경우 엄격한 타입 검사를 수행한 뒤 모두 지원되지 않는 것으로 간주하여 `401 Unauthorized`를 반환하도록 수정해야 합니다.

## 2026-08-21 - ecdsa 취약점 제거 (python-jose 의존성 교체)
**Vulnerability:** `python-jose`가 내부적으로 사용하는 `ecdsa` 라이브러리에 P-256 관련 타이밍 공격(Minerva timing attack, CVE-2024-23342) 취약점이 발견되었습니다.
**Learning:** `python-jose`는 오랫동안 업데이트되지 않아 하위 의존성 보안 이슈에 취약합니다. 이를 방지하려면 보다 활발하게 유지보수되는 라이브러리로 전환하는 것이 중요합니다.
**Prevention:** 백엔드의 JWT 파싱 의존성을 `python-jose`에서 `PyJWT`로 교체하고, `python-jose` 및 관련 타입 의존성을 `pyproject.toml`에서 제거하여 잠재적 취약점 경로를 원천 차단했습니다.

## 2026-08-21 - nanoid 취약점 수정 (의존성 업데이트)
**Vulnerability:** `nanoid` 패키지의 하위 버전에 `0` 사이즈 요청 시 무한 루프에 빠져 Denial of Service(DoS)가 가능한 취약점(CVE-2026-67213, GHSA-2v37-7h3g-55p8)이 존재했습니다.
**Learning:** 서드파티 패키지에 취약점이 보고될 경우, 해당 라이브러리를 명시적으로 최신 안전한 버전으로 강제(override/resolution)하여 하위 의존성까지 일괄 패치해야 함을 확인했습니다.
**Prevention:** `package.json`의 `overrides` 항목을 활용하여 `nanoid` 버전을 `^3.3.18`로 강제 적용함으로써, 중첩된 하위 패키지들에서도 모두 안전한 버전을 사용하도록 설정했습니다.
