# API Security Checklist (pg-erd-cloud)

이 문서는 pg-erd-cloud의 **backend HTTP API**(FastAPI) 기준으로, 설계/구현/
배포/운영에서 확인해야 할 보안 체크리스트를 정리한 것입니다.

> 주의: OWASP API Security Top 10은 **CC BY-SA 4.0**(ShareAlike) 라이선스
> 문서이므로, 본 문서는 내용을 복제하지 않고 **링크와 개념 매핑**만 제공합니다.

## References (patterns only)

- shieldfy/API-Security-Checklist (MIT):
  <https://github.com/shieldfy/API-Security-Checklist>
- OWASP API Security Top 10 (CC BY-SA 4.0): <https://owasp.org/API-Security/>

## Scope

- 대상: `backend/app/*` API (예: `/api/projects`, `/api/snapshots`)
- 비대상(별도 문서화 필요): 인프라 계층(WAF/API Gateway/Ingress), 관측(로그/메트릭/알림), 조직 정책(Rulesets)

## Checklist

표기:

- ✅: 현재 코드/CI에서 충족(또는 강제)
- 🟡: 부분 충족(운영/배포 설정에 따라 달라짐)
- ⏳: 미구현(후속 작업 필요)

### Authentication

- ✅ Basic Auth 미사용 (OIDC Bearer Token 또는 dev fallback)
  - 근거: `backend/app/auth.py`
- ✅ JWT 검증 시 알고리즘 allowlist 강제(토큰 헤더 alg 신뢰 금지)
  - 설정: `OIDC_ALGORITHMS` (default: `RS256`)
  - 근거: `backend/app/auth.py`, `backend/app/settings.py`
- 🟡 토큰 TTL/Refresh 정책(권장: 짧게) — IdP(Casdoor) 설정에 의존

### Authorization

- ✅ 프로젝트 리소스 접근은 멤버십 기반으로 제한
  - 근거: `backend/app/permissions.py`, 각 API handler에서 `require_project_member(...)`
- 🟡 공유 링크(공개 엔드포인트)는 최소 권한(읽기)만 제공
  - 근거: `backend/app/api/share.py`

### Access / Abuse Prevention

- ⏳ Rate limiting / throttling (API Gateway/WAF 또는 앱 레이어) — tracked: #47
- 🟡 HTTPS/TLS/HSTS는 인그레스/리버스프록시 계층에서 강제 필요
- 🟡 CORS(CORSMiddleware) 설정 검증
  - 근거: `backend/app/main.py` (CORSMiddleware 설정)
  - 체크 포인트:
    - `allow_origins`는 최소 허용(정확한 allowlist)으로 유지
    - `allow_methods`/`allow_headers`는 가능한 한 명시적 allowlist로 제한
      (예: GET/POST/OPTIONS, Authorization/Content-Type 등)
    - public API라면 `allow_credentials=True` 필요성 재검토(필요 시에만; 기본은 False 권장)
    - ingress/ALB 등 외부 계층에서도 동일 정책(또는 더 엄격한 정책)을 적용했는지 확인

### Input validation

- ✅ 민감정보를 URL로 받지 않음(권장: Authorization header)
- ✅ 문자열 입력에서 NUL(0x00) 제거(특히 PostgreSQL text/json 방어)
  - 근거: `backend/app/sanitize.py`
- 🟡 스키마명 등 일부 입력은 제한(예: PostgreSQL identifier)
  - 근거: `backend/app/schemas.py` (`schema_filter` 패턴/길이 제한)

### Processing / DoS 방어

- ✅ 요청 경로에서 장시간 작업을 블로킹하지 않음(큐/워커)
  - 근거: `backend/app/jobs/*`, `backend/app/main.py`(lifespan worker)
- ✅ PK/FK 등 고유 식별자는 UUID 사용
  - 근거: Alembic migrations / ORM models

### Output / Response hardening

- ⏳ 보안 응답 헤더(CSP/XFO/nosniff 등)는 (1) ingress/proxy에서 일괄 적용하거나
  (2) FastAPI middleware로 추가 적용 검토 — tracked: #48
- ✅ 오류 메시지는 과도한 내부정보를 노출하지 않도록 일반화(상세는 서버 로그로)
  - 근거: `backend/app/auth.py` 등(HTTPException detail)

### CI / CD / Supply chain

- ✅ Code scanning(CodeQL) + dependency review + Scorecard 워크플로 운영
  - 근거: `.github/workflows/*`
- ✅ GitHub Actions `uses:` SHA pinning
  - 근거: `.github/workflows/*`

### Monitoring

- ⏳ 중앙 로그/메트릭/알림(운영 환경별 설계 필요) — tracked: #49
