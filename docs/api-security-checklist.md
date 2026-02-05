# API Security Checklist (MVP)

이 문서는 `pg-erd-cloud`의 **API 보안 통제**를 추적/점검하기 위한 체크리스트입니다.

## Access / Abuse Prevention

### Rate limiting / throttling

상태: ✅ (FastAPI 앱 레이어 1차 적용)

#### 적용 범위

- 기본: `/api/*` 요청
- 제외: `/healthz` 등 `/api` 밖 경로

#### 동작

- 동일 key(기본: **IP** + (가능하면) **OIDC subject**) 기준으로 고정 윈도우 방식 제한
- 초과 시 `429 Too Many Requests` + `Retry-After` 헤더 반환

#### 운영 설정 (env)

`.env` 또는 배포 환경변수로 정책을 조정할 수 있습니다.

- `API_RATE_LIMIT_ENABLED` (default: `true`)
- `API_RATE_LIMIT_REQUESTS` (default: `120`)
- `API_RATE_LIMIT_WINDOW_SECONDS` (default: `60`)
- `API_RATE_LIMIT_TRUST_X_FORWARDED_FOR` (default: `false`)
  - 프록시/Ingress가 `X-Forwarded-For`를 신뢰 가능한 형태로 세팅/정제하는 경우에만 `true`
- `API_RATE_LIMIT_MAX_KEYS` (default: `10000`)

#### Trade-offs / 향후 계획

현재 구현은 **프로세스(in-memory) 단위**로 동작합니다.

- 멀티 워커/멀티 인스턴스 환경에서는 전역(global) 제한이 아니라 **각 워커/인스턴스별 제한**이 됩니다.
- 필요 시 2차 개선으로 Redis/Valkey 같은 공유 스토어 기반으로 확장합니다.

## Monitoring

상태: ⏳ (1차: 구조화 로그 + 최소 메트릭)

범위(요약): 요청량/지연(p95)/오류율(4xx/5xx), 인증·권한 실패, 큐 적체(대기/처리시간)
등을 관측하고, 임계치 초과 시 운영자가 즉시 원인 파악/완화(롤백·스케일·차단)할 수 있도록
알림을 연결합니다.

- 문서: `docs/observability.md`
