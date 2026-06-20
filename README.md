# pg-erd-cloud (MVP skeleton)

PostgreSQL 전문 클라우드 ERD(협업/공유) 소프트웨어의 **실행 가능한 MVP 골격**입니다.

## 제공 기능(현재)

- **Backend DB = PostgreSQL** (앱 메타데이터 저장)
- **Reverse engineering(리버스)**: 대상 PostgreSQL에 연결해서
  - schema/table/column
  - PK/FK/UNIQUE/CHECK
  - index (access method 포함, 예: btree/hash/gist/gin/spgist/brin + extension AM)
  를 pg_catalog 기반으로 수집하고 스냅샷으로 저장
- **ERD UI**: React Flow(MIT)로 PK/FK를 그래픽으로 렌더링
- **Forward engineering(포워드)**: MVP 단계에서는 “스냅샷 기반 DDL(export)” 중심
  (diff/변경 SQL 생성은 로드맵)

  - SQL export: `GET /api/snapshots/{snapshot_uuid}/export.sql`

## 공유(동료에게 링크 공유)

프로젝트 오너는 공유 링크를 생성할 수 있습니다.

```bash
curl -X POST "http://localhost:8000/api/projects/<project_uuid>/share-links" \
  -H "X-Dev-User: alice"
```

반환된 `url_path`로 동료가 최신 스냅샷 목록/스냅샷 JSON/DDL export를 조회할 수 있습니다.

## 인덱스 타입 지원 원칙

PostgreSQL은 `CREATE INDEX ... USING <method>`의 `<method>`가
기본(btree/hash/gist/gin/spgist/brin)뿐 아니라 **확장(extension)으로 추가된 access method**도
될 수 있습니다.

따라서 본 프로젝트는 **고정된 목록을 하드코딩하지 않고**,

- `pg_am` + `pg_class.relam`로 “현재 DB에 실제로 존재하는 access method
  (amname)”를 수집
- `pg_get_indexdef()`로 DDL을 **손실 없이** 보존

하는 방식으로 “현존(해당 DB에 설치된) 인덱스 타입”을 폭넓게 지원합니다.

근거(공식 문서):

- Index types / extension bloom 예시:
  <https://www.postgresql.org/docs/current/indexes-types.html>
- CREATE INDEX (user-installed access methods):
  <https://www.postgresql.org/docs/current/sql-createindex.html>
- pg_am / pg_class / pg_index:
  <https://www.postgresql.org/docs/current/catalog-pg-am.html>
- pg_get_indexdef / pg_get_expr:
  <https://www.postgresql.org/docs/current/functions-info.html>

## 실행(로컬, Docker)

```bash
cp .env.example .env
docker compose up -d --build
```

- Frontend: <http://localhost:5173>
- Backend: <http://localhost:8000> (health: /healthz)

## 실행(프로덕션 스타일, Docker)

Traefik을 edge router로 사용합니다. `/api/*`와 `/healthz`는 백엔드로 라우팅하고,
나머지 경로는 정적 빌드된 프론트엔드 SPA로 라우팅합니다.

```bash
cp .env.example .env

# 프로덕션 스타일에서는 Docker secret 파일로 APP_SECRET을 주입합니다.
# (이 파일은 커밋 금지: .gitignore에 **/secrets/** 포함)
mkdir -p secrets
python - <<'PY'
import secrets

with open('secrets/app_secret', 'w', encoding='utf-8') as f:
    f.write(secrets.token_urlsafe(48) + "\n")
PY

# Restrict secret file permissions (owner read/write only)
chmod 600 secrets/app_secret

docker compose -f compose.prod.yaml up -d --build
```

- App entrypoint: <http://localhost:8080> (`TRAEFIK_HTTP_PORT`로 변경 가능)
- Health: <http://localhost:8080/healthz>

### Azure VMSS 상태 프로브(선택)

VMSS Application Health Extension을 사용할 경우 `/healthz` 프로브 설정 예시는 아래 문서를
참고하세요.

- [Azure VMSS Application Health Extension 가이드](docs/azure-vmss-health-extension.md)

## 개발(비-Docker)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -e .
alembic upgrade head
hypercorn --config python:app.hypercorn_config app.main:app \
  --bind 0.0.0.0:8000 --reload \
  --access-logfile - --error-logfile -
```

#### 운영 팁

- Hypercorn worker 수는 `HYPERCORN_WORKERS`(또는 `WEB_CONCURRENCY`)로 조절할 수
  있습니다.
- `APP_SECRET`은 앱 DB에 저장되는 DSN 암호화 키로 사용되므로, 변경 시 기존 데이터
  복호화에 영향을 줄 수 있습니다. 가능하면 `APP_SECRET_FILE`(예:
  `/run/secrets/app_secret`) 방식으로 안전하게 주입하세요.

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

## 보안/운영 주의

- `.env`는 커밋 금지(이미 .gitignore에 포함).
- 대상 DB 연결정보(DSN)는 **APP_SECRET** 기반으로 암호화하여 앱 DB에 저장합니다.
- 역공학(리버스) 작업은 요청 경로에서 동기 대기하지 않고 job queue로 비동기 처리합니다.
- API 보안 체크리스트(프로젝트 기준): [docs/api-security-checklist.md](docs/api-security-checklist.md)

## 로드맵(요약)

- Casdoor OIDC 로그인 UI/리다이렉트 플로우(현재는 토큰 검증/DEV 모드만)
- 실시간 협업(커서/코멘트/CRDT 기반 동시 편집)
- 포워드 엔지니어링(diff 기반 변경 SQL 생성/검증)
