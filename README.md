# pg-erd-cloud (MVP skeleton)

PostgreSQL 중심 클라우드 ERD(협업/공유) 소프트웨어의 **실행 가능한 MVP 골격**입니다.

## 제공 기능(현재)

- **Backend DB = PostgreSQL** (앱 메타데이터 저장)
- **Reverse engineering(리버스)**: 대상 PostgreSQL에 연결해서
  - schema/table/column
  - PK/FK/UNIQUE/CHECK
  - index (access method 포함, 예: btree/hash/gist/gin/spgist/brin + extension AM)
  를 pg_catalog 기반으로 수집하고 스냅샷으로 저장
- **Snowflake reverse engineering(선택)**: `snowflake://user:password@account/database/schema`
  형식의 DSN을 사용하면 Snowflake `INFORMATION_SCHEMA`에서 schema/table/column,
  PK/UNIQUE/FK 메타데이터를 수집하고 `source_dialect: "snowflake"` 스냅샷으로 저장합니다.
  실행 환경에는 선택 의존성 `snowflake-connector-python`이 필요합니다.
- **ERD UI**: React Flow(MIT)로 PK/FK를 그래픽으로 렌더링
- **Forward engineering(포워드)**: MVP 단계에서는 “스냅샷 기반 DDL(export)” 중심
  (diff/변경 SQL 생성은 로드맵)

  - SQL export: `GET /api/snapshots/{snapshot_uuid}/export.sql`
  - Target dialect: `?dialect=postgresql`(기본값) 또는 `?dialect=snowflake`
    - PostgreSQL 스냅샷을 Snowflake DDL로 변환할 때 주요 column type을 매핑하고,
      PostgreSQL 전용 index/tablespace/partition/check constraint는 주석으로 보존합니다.
    - Snowflake reverse snapshot JSON(`source_dialect: "snowflake"`)도 PostgreSQL
      DDL export에서 주요 type을 매핑합니다.
- **DB Reversing 명세서 생성**:
  - Markdown draft: `GET /api/snapshots/{snapshot_uuid}/reversing-spec.md`
  - LLM prompt: `GET /api/snapshots/{snapshot_uuid}/reversing-spec.md?mode=llm-prompt`
  - Live LLM draft: `GET /api/snapshots/{snapshot_uuid}/reversing-spec.md?mode=llm-draft`
    - `LLM_API_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`을 설정한 OpenAI-compatible
      chat-completions provider를 호출합니다.
    - `LLM_MAX_PROMPT_CHARS`와 `LLM_MAX_OUTPUT_TOKENS`로 prompt 크기와 provider
      출력 토큰 상한을 제한합니다.
  - Share link에서도 동일한 `/api/share/{share_uuid}/snapshots/{snapshot_uuid}/...`
    경로를 사용할 수 있습니다. 단, 공개 공유 링크의 `mode=llm-draft`는
    `SHARE_LINK_LLM_DRAFT_ENABLED=true`로 명시적으로 허용하기 전까지 차단됩니다.
- **컬럼 예시값 힌트**: 리버스 스냅샷의 각 컬럼에 `example_value`를 추가합니다.
  실제 테이블 데이터를 샘플링하지 않고 컬럼명/타입 메타데이터로 만든 합성 예시라서
  ERD, PlantUML/SVG export, 명세서, LLM prompt에서 안전하게 참고할 수 있습니다.

## 공유(동료에게 링크 공유)

프로젝트 오너는 공유 링크를 생성할 수 있습니다.

```bash
curl -X POST "http://localhost:8000/api/projects/<project_uuid>/share-links"
```

반환된 `url_path`로 동료가 최신 스냅샷 목록/스냅샷 JSON/DDL export를 조회할 수 있습니다.
공유 링크는 기본적으로 `SHARE_LINK_DEFAULT_TTL_HOURS=168`(7일) 뒤 만료됩니다.
오너는 `GET /api/projects/{project_uuid}/share-links`로 링크를 조회하고,
`DELETE /api/projects/{project_uuid}/share-links/{share_uuid}`로 폐기할 수 있습니다.
`/api/share/*` 공개 조회/내보내기 경로는 전역 `/api/*` 제한보다 더 엄격한 별도
IP 기반 rate limit을 적용합니다.
공유 링크의 `markdown`/`llm-prompt` export는 로컬 생성만 수행하지만, `llm-draft`
export는 외부 LLM provider 비용을 만들 수 있으므로 기본값에서 비활성화되어 있습니다.

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

# compose.prod.yaml은 APP_ENV=production으로 실행됩니다. 아래 값을 localhost가 아닌
# 운영 값으로 바꾸세요. 누락되면 백엔드는 시작 단계에서 실패합니다.
# - OIDC_ISSUER / OIDC_AUDIENCE
# - CORS_ORIGINS=https://erd.example.com
# - DB_INTROSPECTION_ALLOWED_HOSTS=db.example.com,*.internal.example.com

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

Snowflake 리버스 엔지니어링을 사용할 개발 환경에서는 백엔드 가상환경에서 선택 의존성을
함께 설치합니다.

```bash
pip install -e ".[snowflake]"
```

#### 운영 팁

- Hypercorn worker 수는 `HYPERCORN_WORKERS`(또는 `WEB_CONCURRENCY`)로 조절할 수
  있습니다.
- `APP_SECRET`은 앱 DB에 저장되는 DSN 암호화 키로 사용되므로, 변경 시 기존 데이터
  복호화에 영향을 줄 수 있습니다. 가능하면 `APP_SECRET_FILE`(예:
  `/run/secrets/app_secret`) 방식으로 안전하게 주입하세요.
- `APP_ENV=production`에서는 OIDC, 공개 HTTPS CORS origin, 대상 DB allowlist,
  32자 이상의 secret, 공유 링크 기본 만료가 startup guard로 강제됩니다.

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
