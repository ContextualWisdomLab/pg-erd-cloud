## $(date +%Y-%m-%d) - Redact Sensitive Schema Comments in Public Shares
**Vulnerability:** Publicly shared schema snapshots (via `/api/share/...`) returned the entire JSON payload, which could expose sensitive internal schema comments (`comment`, `relation_comment`, `column_comment`) or sensitive data in `example_value` fields.
**Learning:** When generating share links, only specific fields should be exposed, but we export the entire `snapshot_json` from the database. A recursive sanitizer function must be applied to scrub IDOR/data leakage vectors before returning the JSON payload.
**Prevention:** Apply a recursive masking function (`_redact_sensitive_snapshot_fields`) on database JSON artifacts in read-only public endpoints.

## 2025-02-14 - JWT crit(critical) 헤더 검증 누락 수정
**Vulnerability:** JWT 파싱 과정에서 RFC 7515에 명시된 `crit` (critical) 헤더에 대한 명시적 검증 로직이 존재하지 않아, 서명된 토큰이 인식 불가능한 중요 확장자(critical extensions) 처리를 요구하더라도 이를 무시하고 통과시킬 수 있는 잠재적 우회 취약점이 있었습니다.
**Learning:** PyJWT와 같은 라이브러리를 사용할 때 기본 옵션만으로는 JWS 명세의 모든 보안 요구사항(특히 `crit` 파라미터)이 자동으로 강제되지 않을 수 있음을 확인했습니다.
**Prevention:** `_validate_jwt_header` 함수에서 `crit` 헤더가 존재하는지 명시적으로 확인하고, 배열 타입 및 길이 제한을 적용하며, 현재 어플리케이션은 어떠한 추가 critical 파라미터도 지원하지 않으므로 항목이 존재할 경우 무조건 예외를 발생시키도록 방어적 검증 로직을 추가했습니다.

## 2025-02-14 - python-jose 취약점(PYSEC-2026-1325) 완화를 위한 PyJWT 전환
**Vulnerability:** `python-jose` 라이브러리가 더 이상 유지보수되지 않고 있으며, 내부적으로 사용하는 `ecdsa` 라이브러리의 취약점(PYSEC-2026-1325)을 그대로 상속받고 있었습니다. 이로 인해 CI의 OSV 스캔 및 dependency review에서 크리티컬한 보안 취약점 경고가 발생했습니다.
**Learning:** 의존성 취약점이 프로젝트의 보안에 미치는 영향을 다시 확인했습니다. 특히, 유지보수가 중단된 보안 라이브러리의 경우 발견된 취약점이 수정되지 않아 이를 신속하게 교체해야 합니다.
**Prevention:** `backend/pyproject.toml`에서 `python-jose` 및 `types-python-jose` 의존성을 제거하고 `PyJWT`로 완전히 전환했습니다. 이에 따라 JWT 서명 검증 및 디코딩 로직에 사용하는 모듈을 `import jwt` (PyJWT)로 교체하고 관련 테스트들을 업데이트했습니다.

## 2025-02-14 - PyJWT migration decode options
**Learning:** `PyJWT`의 `decode` 함수는 `options` 매개변수에 대해 `python-jose`와 다르게 `require_aud`, `require_iss`, `require_exp` 등의 키를 지원하지 않으며, 알 수 없는 키가 전달되면 `ValueError`를 발생시킵니다. 대신 `require` 리스트(`["exp", "iss", "jti", "aud"]`) 형태로 검증 옵션을 지정해야 합니다. 또한, `jti`를 강제하기 위해 기존 `python-jose` 옵션을 변환할 때 필수적으로 `require` 리스트에 `jti`를 포함시켜야 합니다.
**Prevention:** `jwt.decode` 사용 시, `options={"require": ["exp", "iss", "jti", ...], "verify_aud": True}`와 같이 PyJWT 스펙에 맞춰 `options` 딕셔너리를 올바르게 구성했습니다.

## 2025-02-14 - PyJWT crit parameter null 우회 버그 수정
**Vulnerability:** JWT 헤더를 검사하는 `_validate_jwt_header`에서 파이썬 dict의 `get` 메서드를 사용하여 `crit = header.get("crit")`로 값을 가져올 때, 페이로드에 실제로 `{"crit": null}` 이 포함되어 있으면 `crit is not None` 조건에 걸리지 않아 (null이 파이썬 None으로 매핑됨) 검증을 그대로 우회할 수 있습니다.
**Learning:** JSON 검증에서 키의 존재 여부와 키의 값이 None인지를 구분해야 합니다. `dict.get()`을 사용하여 검증을 우회할 수 있는 edge case(Null Injection)가 생길 수 있음을 확인했습니다.
**Prevention:** `if "crit" in header:` 와 같이 키가 헤더에 명시적으로 존재하는지 확인한 뒤에 처리하도록 코드를 방어적으로 작성했습니다. 이로 인해 어떤 형태로든 `crit` 필드를 포함한 모든 JWT가 차단됩니다.

## 2025-02-14 - PyJWT crit parameter null 우회 버그 수정
**Vulnerability:** JWT 헤더를 검사하는 `_validate_jwt_header`에서 파이썬 dict의 `get` 메서드를 사용하여 `crit = header.get("crit")`로 값을 가져올 때, 페이로드에 실제로 `{"crit": null}` 이 포함되어 있으면 `crit is not None` 조건에 걸리지 않아 (null이 파이썬 None으로 매핑됨) 검증을 그대로 우회할 수 있습니다.
**Learning:** JSON 검증에서 키의 존재 여부와 키의 값이 None인지를 구분해야 합니다. `dict.get()`을 사용하여 검증을 우회할 수 있는 edge case(Null Injection)가 생길 수 있음을 확인했습니다.
**Prevention:** `if "crit" in header:` 와 같이 키가 헤더에 명시적으로 존재하는지 확인한 뒤에 처리하도록 코드를 방어적으로 작성했습니다. 이로 인해 어떤 형태로든 `crit` 필드를 포함한 모든 JWT가 차단됩니다.
