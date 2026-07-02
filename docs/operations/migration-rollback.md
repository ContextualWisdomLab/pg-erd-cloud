# Migration Rollback Policy

이 문서는 운영 중 DB 마이그레이션 실패 또는 기능 이상이 탐지되었을 때
`alembic` 기준 안전하게 롤백하는 절차를 제공합니다.

## 원칙

- **원인 규명이 끝나기 전 임시 조치**: 추가 데이터 손상을 막기 위해 우선 읽기
  트래픽을 제한하거나 필요한 API 노출을 줄입니다.
- **항상 사전 검증**: 본환경 rollback은 격리 환경에서 사전 검증 후 실행합니다.
- **증거 보존**: `HEAD`, `alembic history`, 배포 커밋 해시를 이벤트 기록에 남깁니다.

## 실행 기준

- `alembic current` 결과가 코드 레벨의 `alembic head`와 다를 때
- 배포 후 10분 이내 핵심 API가 연속 실패하거나 데이터 무결성 이상이 확인될 때

## 사전 점검

```bash
cd backend
alembic current
alembic history --verbose | head -n 20
```

현재 데이터베이스 revision을 `HEAD`와 비교합니다.

## 단계별 롤백 절차

### 1) 위험 완화

- 웹/공유 공개 라우팅에서 영향 범위를 줄입니다.
- 필요 시 일시적으로 `SHARE_LINK_LLM_DRAFT_ENABLED=false`와 라우트 제한을 강화합니다.

### 2) 롤백 대상 선정

- 실패 원인이 마지막 마이그레이션(예: `abcd1234`)으로 확인되면 `--sql` 모드로
  문법/결과를 예행연습합니다.

```bash
cd backend
alembic downgrade --sql abcd1234 -1
```

### 3) 스테이징에서 dry-run 확인

- 운영 DB를 직접 건드리지 않고 스테이징 DB에서 동일 절차를 반복합니다.

### 4) 운영 롤백 실행

```bash
docker compose -f compose.prod.yaml run --rm backend alembic downgrade -1
```

필요 시 마지막 2~3개 리비전을 한 번에 되돌리는 경우:

```bash
docker compose -f compose.prod.yaml run --rm backend alembic downgrade -2
```

### 5) 복구 검증

- `alembic current`가 의도한 revision인지 확인
- `/healthz`와 핵심 API smoke test 실행:
  - 프로젝트 조회, 스냅샷 조회, 공유 링크 조회/폐기, SQL export
- 문제가 계속되면 추가 rollback 또는 DB restore drill로 전환합니다.

## 롤백 불가 사례

- 데이터 변형이 영구적인 마이그레이션(대량 데이터 삭제/이관)은 롤백 전에
  백업 유효성 확인 후에만 진행합니다.
- `APP_SECRET` 변경 이력과 앱 DB 암호화 데이터 무결성 검토 없이 복구를 진행하지 않습니다.

## 운영 문서 갱신 규칙

- 롤백이 실제로 발생하면 24시간 이내에 `docs/commercial-readiness.md`의 P1/P0 항목
  상태를 갱신하고, 배포 이슈/PR 본문에 재발 방지 조치를 첨부합니다.
