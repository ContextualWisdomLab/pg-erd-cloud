## $(date +%Y-%m-%d) - Redact Sensitive Schema Comments in Public Shares
**Vulnerability:** Publicly shared schema snapshots (via `/api/share/...`) returned the entire JSON payload, which could expose sensitive internal schema comments (`comment`, `relation_comment`, `column_comment`) or sensitive data in `example_value` fields.
**Learning:** When generating share links, only specific fields should be exposed, but we export the entire `snapshot_json` from the database. A recursive sanitizer function must be applied to scrub IDOR/data leakage vectors before returning the JSON payload.
**Prevention:** Apply a recursive masking function (`_redact_sensitive_snapshot_fields`) on database JSON artifacts in read-only public endpoints.

## 2025-02-14 - JWT crit(critical) 헤더 검증 누락 수정
**Vulnerability:** JWT 파싱 과정에서 RFC 7515에 명시된 `crit` (critical) 헤더에 대한 명시적 검증 로직이 존재하지 않아, 서명된 토큰이 인식 불가능한 중요 확장자(critical extensions) 처리를 요구하더라도 이를 무시하고 통과시킬 수 있는 잠재적 우회 취약점이 있었습니다.
**Learning:** PyJWT와 같은 라이브러리를 사용할 때 기본 옵션만으로는 JWS 명세의 모든 보안 요구사항(특히 `crit` 파라미터)이 자동으로 강제되지 않을 수 있음을 확인했습니다.
**Prevention:** `_validate_jwt_header` 함수에서 `crit` 헤더가 존재하는지 명시적으로 확인하고, 배열 타입 및 길이 제한을 적용하며, 현재 어플리케이션은 어떠한 추가 critical 파라미터도 지원하지 않으므로 항목이 존재할 경우 무조건 예외를 발생시키도록 방어적 검증 로직을 추가했습니다.
