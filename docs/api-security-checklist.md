# API Security Checklist (pg-erd-cloud)

이 문서는 `pg-erd-cloud`의 **backend HTTP API (FastAPI)** 기준으로, 설계/구현/
배포/운영에서 확인해야 할 보안 체크리스트를 정리한 것입니다. 체크리스트 항목은
코드/문서/CI 근거를 함께 남겨 “현재 상태”를 지속적으로 추적하는 것을 목표로
합니다.

> 주의: OWASP API Security Top 10은 **CC BY-SA 4.0**(ShareAlike) 라이선스
> 문서이므로, 본 문서는 내용을 복제하지 않고 **링크와 프로젝트 내부 근거**만
> 제공합니다.

## References (link-only)

- OWASP API Security Project: <https://owasp.org/API-Security/>
- shieldfy/API-Security-Checklist (MIT):
  <https://github.com/shieldfy/API-Security-Checklist>

## Scope

- 대상: `backend/app/*` API (예: `/api/projects`, `/api/snapshots`)
- 포함: 앱 레이어 통제(인증/인가/입력 정화/레이트리밋/관측/응답 헤더) + CI 보안 게이트
- 비대상(별도 통제로 보완 필요):
  - 인프라 계층(WAF/API Gateway/Ingress/Load Balancer)
  - 운영 환경의 모니터링 백엔드(로그 수집/메트릭 스크레이프/알림 채널/대시보드)
  - 조직/리포지토리 정책(Rulesets, 배포 승인 등)

## Status legend

- ✅: 현재 코드/테스트/CI에서 충족(또는 강제)
- 🟡: 부분 충족(운영/배포 설정에 따라 달라짐, 또는 추가 확인 필요)
- ⏳: 미구현(후속 작업 필요)

## Checklist

### Authentication

- ✅ Basic Auth 미사용 (OIDC Bearer Token 또는 dev fallback)
  - 근거: `backend/app/auth.py`
- ✅ JWT 검증 시 알고리즘 allowlist 강제(토큰 헤더 `alg` 신뢰 금지)
  - 설정: `OIDC_ALGORITHMS` (default: `RS256`)
  - 근거: `backend/app/auth.py`, `backend/app/settings.py`
- 🟡 토큰 TTL/Refresh 정책(권장: 짧게) — IdP 설정에 의존(운영 가이드 필요)

### Authorization

- ✅ 프로젝트 리소스 접근은 멤버십 기반으로 제한
  - 근거: `backend/app/permissions.py` 및 각 API handler의
    `require_project_member(...)`
- 🟡 공유 링크(공개 엔드포인트)는 최소 권한(읽기)만 제공
  - 근거: `backend/app/api/share.py`

### CORS

- 🟡 Origin allowlist 기반 설정
  - 설정: `CORS_ORIGINS` (comma-separated)
  - 근거: `backend/app/main.py`, `backend/app/settings.py`
- ✅ 기본값은 `allow_credentials=False` + `allow_methods`/`allow_headers`
  명시적 allowlist를 권장(“reviewable”)
  - 체크 포인트:
    - `allow_origins`는 최소 허용(정확한 allowlist)으로 유지
    - `allow_methods`/`allow_headers`는 가능한 한 명시적 allowlist로 제한
      (예: GET/POST/OPTIONS, Authorization/Content-Type 등)
    - public API라면 `allow_credentials=True` 필요성 재검토(필요 시에만; 기본은 False 권장)
    - ingress/ALB 등 외부 계층에서도 동일 정책(또는 더 엄격한 정책)을 적용했는지 확인

### Access / Abuse Prevention

#### Rate limiting / throttling

상태: ✅ (issue #47, closed; FastAPI 앱 레이어 1차 적용)

- 근거:
  - 구현: `backend/app/rate_limit.py`
  - 적용(wiring): `backend/app/main.py`

##### 적용 범위

- 기본: `/api/*` 요청
- 제외: `/healthz` 등 `/api` 밖 경로

##### 동작

- 동일 key(기본: **IP** + (가능하면) **OIDC subject**) 기준으로 고정 윈도우 방식 제한
- 초과 시 `429 Too Many Requests` + `Retry-After` 헤더 반환

##### 운영 설정 (env)

`.env` 또는 배포 환경변수로 정책을 조정할 수 있습니다.

- `API_RATE_LIMIT_ENABLED` (default: `true`)
- `API_RATE_LIMIT_REQUESTS` (default: `120`)
- `API_RATE_LIMIT_WINDOW_SECONDS` (default: `60`)
- `API_RATE_LIMIT_TRUST_X_FORWARDED_FOR` (default: `false`)
  - 프록시/Ingress가 `X-Forwarded-For`를 신뢰 가능한 형태로 세팅/정제하는 경우에만
    `true`
- `API_RATE_LIMIT_MAX_KEYS` (default: `10000`)

##### Trade-offs / 향후 계획

현재 구현은 **프로세스(in-memory) 단위**로 동작합니다.

- 멀티 워커/멀티 인스턴스 환경에서는 전역(global) 제한이 아니라 **각 워커/인스턴스별
  제한**이 됩니다.
- 필요 시 2차 개선으로 Redis/Valkey 같은 공유 스토어 기반으로 확장합니다.

- 🟡 HTTPS/TLS/HSTS는 인그레스/리버스프록시 계층에서 강제 필요 (앱 단독 강제는 한계)

### Input validation / Data safety

- ✅ 민감정보를 URL로 받지 않음(권장: Authorization header)
- ✅ 문자열 입력에서 NUL(0x00) 제거(특히 PostgreSQL text/json 방어)
  - 근거: `backend/app/sanitize.py`
- 🟡 스키마명 등 일부 입력은 제한(예: PostgreSQL identifier)
  - 근거: `backend/app/schemas.py` (패턴/길이 제한)

### Processing / DoS 방어

- ✅ 요청 경로에서 장시간 작업을 블로킹하지 않음(큐/워커)
  - 근거: `backend/app/jobs/*`, `backend/app/main.py`(lifespan worker)
- ✅ 고유 식별자는 UUID 사용
  - 근거: migrations / models

### Output / Response hardening

- ✅ 응답 보안 헤더(기본 하드닝) 적용 (issue #48, closed; merged via PR #52)
  - 문서: `docs/response-security-headers.md`
  - 근거: `backend/app/security_headers.py` (middleware), `backend/app/main.py`
    (wiring)
  - 🟡 HSTS는 TLS 종료 지점에 따라 유효성이 달라질 수 있으므로, 프로덕션에서는
    ingress/proxy에서의 강제 적용을 우선 고려
- ✅ 오류 메시지는 과도한 내부정보를 노출하지 않도록 일반화(상세는 서버 로그로)
  - 근거: `backend/app/auth.py` 등(HTTPException detail)

### Monitoring / Observability

상태: ✅ (baseline 구현 완료) / 🟡 (운영 연결은 환경 의존) — issue #49, closed

- 문서: `docs/observability.md`
- ✅ 구조화 요청 로그(JSON) + request correlation id
  - 근거: `backend/app/observability.py`
- ✅ 최소 메트릭(HTTP + job queue) 및 `/metrics` 엔드포인트(옵트인)
  - 설정:
    - `OBSERVABILITY_REQUEST_LOGGING_ENABLED` (default: `true`)
    - `OBSERVABILITY_METRICS_ENABLED` (default: `false`)
    - `OBSERVABILITY_METRICS_TOKEN` (required when enabling `/metrics`)
  - 근거: `backend/app/observability.py`, `backend/app/metrics.py`
- 🟡 알림/대시보드/보관정책은 런타임 스택(Kubernetes/VM/managed monitoring 등)에 따라
  별도 구성 필요

### CI / CD / Supply chain

- ✅ Code scanning(CodeQL) + dependency review + Scorecard 워크플로 운영
  - 근거: `.github/workflows/*`
- ✅ GitHub Actions `uses:` SHA pinning
  - 근거: `.github/workflows/*.yml`
