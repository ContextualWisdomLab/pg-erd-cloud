# Product / Technical Gap Baseline

기준일: 2026-09-03

이 문서는 `pg-erd-cloud`의 코드와 운영 증거에서 확인되는 상용화 Gap만 추적한다. 구현되지 않은 기능을 완료된 것처럼 기록하지 않는다. ERD 프로젝트·스키마·다이어그램·주석·API 키에 관한 도메인 truth는 이 저장소가 소유하고, 조직 공통 CI·보안·릴리스 정책은 `ContextualWisdomLab/.github`의 released contract를 따른다.

## 현재 경계

- Backend: FastAPI + SQLAlchemy/Alembic 기반의 ERD/스키마 관리 API.
- Frontend: TypeScript/Vite.
- 배포: Docker Compose 및 Traefik 경계.
- 외부 공통 책임은 소스 복제로 들여오지 않고 versioned owner contract로 소비한다.

## Code-current Gap

### G-SEC-001 — 식별자 제어 문자 검증

`DiagramViewCreateIn.name`, `ApiKeyCreateIn.key_name`은 제품 수준의 라벨로 간주되어 ASCII C0 제어 문자와 DEL을 거부해야 한다. 반면 데이터베이스 식별자 도메인인 `TableAnnotationUpsertIn.schema_name`, `TableAnnotationUpsertIn.relation_name`은 PostgreSQL의 식별자 규칙을 준수하여(NUL을 제외한 모든 문자 허용) 개행 및 탭과 같은 문자를 보존해야 한다. `TableAnnotationUpsertIn.body`처럼 실제 멀티라인 콘텐츠를 담는 필드도 개행/탭을 보존해야 한다. 데이터베이스 식별자에 대한 무조건적인 제어 문자 필터링은 식별자 무결성을 훼손하므로 적용하지 않아야 한다.

- 회귀 증거: 새로 추가된 `test_table_annotation_postgres_identity.py`에서 `schema_name`, `relation_name` 필드가 제어 문자(LF, TAB 등)를 올바르게 보존하는지 검증한다. 제품 라벨 필드는 별도로 `test_schema_control_characters.py`에서 제어 문자를 검증한다.
- 남은 조건: exact-head backend test/lint/security가 실제 runner에서 실행되어 GREEN이어야 한다. CodeQL `startup_failure`나 queued 상태는 성공 증거가 아니다.

### G-CONFIG-001 — 런타임 secret/config KV 전환

현재 저장소 지침이 명시하듯 `backend/app/settings.py`의 `BaseSettings` 기반 환경변수 직접 로딩은 조직의 런타임 KV/credential-registry 경계에 대한 알려진 편차다. `app_secret`, database URL, LLM/OIDC/Valkey 자격정보는 환경변수를 런타임 source of truth로 사용하지 않고 bootstrap 단계에서 KV에 적재한 뒤 애플리케이션은 KV만 읽도록 이관해야 한다.

완료 조건은 다음과 같다.

- bootstrap transport와 runtime read 경계를 분리한다.
- secret 값은 로그·trace·exception에 남지 않는다.
- tenant/credential lookup 실패가 fail-closed 한다.
- 기존 환경변수 직접 읽기를 제거하는 테스트와 migration/rollback 절차가 있다.

### G-REL-001 — immutable release 부재

2026-09-03 live GitHub Releases 조회 결과 canonical release가 0개다. 상용 배포 완료를 주장하려면 protected head에서 version/CHANGELOG/tag/package를 일치시키고 SBOM, provenance, 재현성 및 rollback 증거를 포함한 immutable release를 실제 발행해야 한다.

완료 조건은 release artifact가 source SHA와 추적 가능하고, consumer가 mutable branch/head가 아니라 그 release/version을 사용하며, rollback rehearsal이 동일 artifact identity를 기준으로 재현되는 것이다.

## 현재 병합 판단

제어 문자 hardening 자체는 production contract와 focused regression test를 갖췄지만, required exact-head workflow가 terminal GREEN이 될 때까지 merge-ready로 간주하지 않는다. 조직 runner/CodeQL control-plane 장애는 leaf 저장소의 gate 완화나 no-op commit으로 우회하지 않고 `.github` owner path에서 복구한다.
