# Product / Technical Gap Baseline

이 문서는 pg-erd-cloud의 상용화 Gap을 live code, protected branch, 열린 PR, 실행 테스트를 기준으로 누적 관리한다. 자동 생성 설명이나 scanner suppression보다 실제 DB-API 경계와 exact-head 검증을 우선한다.

## MySQL / MariaDB metadata introspection

### 문제

스키마 선택값은 사용자·외부 연결 설정에서 들어오지만 `information_schema` 조회문의 SQL 구조를 바꿀 이유가 없다. selector를 문자열 조각으로 만든 뒤 f-string으로 `WHERE` 절에 넣으면 현재 값이 placeholder로만 구성돼 있더라도 SQL 구조가 runtime data flow에 의존하게 되고, Bandit B608 suppression을 유지해야 한다. 이 방식은 parameterization contract를 코드와 테스트에서 명확히 증명하기 어렵다.

### 선택

- 네 개 metadata query는 module-level static SQL로 유지한다.
- 선택된 schema와 제외할 system schema는 모두 DB-API `%s` parameter로만 전달한다.
- `# nosec B608`는 사용하지 않는다. scanner 예외가 아니라 실행 구조가 안전 경계를 표현해야 한다.
- connection lifecycle은 성공·실패 여부와 무관하게 `finally`에서 닫는다.

### RED / GREEN evidence

- RED `40aae6f001615b8ee1199f592c5504eb5215984f`: quote, SQL operator, comment marker와 newline이 섞인 schema selector가 SQL text에 나타나지 않고 parameter tuple에만 존재하는지 recording cursor로 검증한다. connection close와 B608 suppression 부재도 함께 고정한다.
- GREEN `67ae24076ef9a071e50d127079d408ba0b01f8e5`: runtime WHERE interpolation을 제거하고 static metadata statements와 parameter-only selector tuple을 적용한다.
- Scope repair `a5d7704d81f6ce7edcec28024d912db8852ef8a3`: unrelated schema-validation/lockfile delta를 제거한다.
- Regression `8146cb6cd8b5ba26c5f9103facc0808efbce17c5`: descendant가 `WHERE {where}`와 `# nosec B608`를 다시 넣고 focused regression을 삭제했다.
- Repair `730bc0965c633c2e1cc8491c6098265446a68f2b` / `8cf45febfb27ab35856f8fa0666ecedd7ab726ff`: history를 재작성하지 않고 static SQL과 regression test를 복구했다.

### Acceptance

protected `main@8dc746920c12988f082e914879d95e13c9693535`의 descendant exact head에서 backend/frontend와 security/review required checks가 terminal GREEN이어야 한다. predecessor 결과, scanner suppression, source-neutral retrigger, administrator bypass는 acceptance가 아니다.

### 남은 Gap

실제 MySQL과 MariaDB 지원 버전에 대해 read-only account로 metadata query contract를 검증하는 integration fixture가 필요하다. 테스트 환경은 system schema 제외, explicit schema filter, table/view/PK/FK/index mapping과 connection cleanup을 실제 서버에서 확인해야 하며 synthetic unit fixture만으로 release acceptance를 대체하지 않는다.
