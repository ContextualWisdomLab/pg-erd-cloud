# API Security Checklist (pg-erd-cloud)

Status date: 2026-08-09
Lifecycle: application controls are mixed `implemented_on_main`/`active_pr`;
edge and organization controls are `downstream`
Owner: application security maintainers; deployment owners for external controls

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
- ✅ 기본값은 `allow_credentials=False` + 실제 라우터가 사용하는
  `GET`/`POST`/`PUT`/`DELETE`/`OPTIONS` 및 헤더 allowlist
  명시적 allowlist를 권장(“reviewable”)
  - 체크 포인트:
    - `allow_origins`는 최소 허용(정확한 allowlist)으로 유지
    - `allow_methods`/`allow_headers`는 가능한 한 명시적 allowlist로 제한
      (예: GET/POST/PUT/DELETE/OPTIONS, Authorization/Content-Type 등)
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
- `API_RATE_LIMIT_TRUSTED_PROXY_HOPS` (default: `1`)
  - 신뢰할 `X-Forwarded-For` 주소를 오른쪽에서 몇 번째 hop으로 읽을지 정합니다.
  - `compose.prod.yaml`은 백엔드를 호스트에 공개하지 않고 Traefik만 경유시킵니다.
    loopback port 앞의 host-local TLS terminator가 Docker NAT를 거친 뒤 Traefik에
    보이는 최소 direct-peer `/32` 또는 `/128` CIDR을
    `TRAEFIK_TRUSTED_PROXY_CIDRS`에 allowlist하고, `client, trusted-peer` 체인의 두
    번째 hop을 읽도록 값을 `2`로 재정의합니다. 체인이 더 짧으면 헤더를 쓰지 않고
    direct peer로 안전하게 fallback합니다.
- `API_RATE_LIMIT_MAX_KEYS` (default: `10000`)

##### Trade-offs / 향후 계획

현재 구현은 **프로세스(in-memory) 단위**로 동작합니다.

- 멀티 워커/멀티 인스턴스 환경에서는 전역(global) 제한이 아니라 **각 워커/인스턴스별
  제한**이 됩니다.
- 필요 시 2차 개선으로 Redis/Valkey 같은 공유 스토어 기반으로 확장합니다.

- 🟡 HTTPS/TLS/HSTS는 인그레스/리버스프록시 계층에서 강제 필요 (앱 단독 강제는 한계)

### Input validation / Data safety

- 🟡 일반 인증정보는 URL로 받지 않지만, 공개 공유의
  `/share/{share_link_uuid}`는 URL 자체가 bearer capability입니다. 브라우저 기록,
  복사, 프록시/분석 로그, referrer 유출을 전제로 취급하고 응답에는
  `Referrer-Policy: no-referrer`와 `Cache-Control: no-store`를 유지합니다.
- ✅ 문자열 입력에서 NUL(0x00) 제거(특히 PostgreSQL text/json 방어)
  - 근거: `backend/app/sanitize.py`
- 🟡 스키마명 등 일부 입력은 제한(예: PostgreSQL identifier)
  - 근거: `backend/app/schemas.py` (패턴/길이 제한)

### Processing / DoS 방어

- 🟡 스냅샷 introspection은 요청 경로를 블로킹하지 않고 큐/워커를 사용합니다.
  단, deprecated `/apply-sql`은 대상 DB에서 동기 실행되므로 production Forward
  Engineering의 durable job 증거가 아닙니다.
  - 근거: `backend/app/jobs/*`, `backend/app/main.py`, `backend/app/api/connections.py`
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

- 🟡 CodeQL/dependency review/Scorecard/Security Scan은 조직의 downstream required
  workflow로 PR에서 실행됩니다. 이 저장소의 `.github/workflows/`에는 일반 CI만
  있으므로 중앙 거버넌스의 실행 결과를 exact head에 연결해야 합니다.
  - 근거: GitHub PR required checks, `.github/workflows/ci.yml`
- ✅ GitHub Actions `uses:` SHA pinning
  - 근거: `.github/workflows/*.yml`
