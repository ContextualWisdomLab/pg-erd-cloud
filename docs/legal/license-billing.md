# 라이선스 및 결제 준비 문서

이 문서는 pg-erd-cloud를 SaaS/온프레미스 배포 시 최소한의 상용 운영 기준을 정리합니다.

## 1) 상용 배포 모드

현재 서비스는 다음 두 가지 운영 모드를 지원합니다.

- `LICENSE_MODE=off`
  - 라이선스 키 검사 미적용
  - 커뮤니티/평가용 기본 동작
- `LICENSE_MODE=required`
  - `/api/projects`, `/api/connections`, `/api/snapshots`, `/api/me`, `/api/auth/*`
    라우트가 `X-LICENSE-KEY` 헤더를 필수로 요구합니다.
  - 환경 변수 `LICENSE_KEY` 또는 `LICENSE_PUBLIC_KEY` 중 하나가 필요합니다.

## 2) 라이선스 키 운영 기본값

- 최소 길이 24자 이상
- 배포마다 랜덤 키를 발급하고 저장소에 커밋하지 않습니다.
- 값은 비밀로 관리하고 정기적으로 교체합니다.
- 노출 또는 유출 의심 시 `LICENSE_KEY`를 즉시 교체합니다.

## 3) 서명 라이선스 토큰 운영

상용 온프레미스 배포는 정적 공유 키보다 `LICENSE_PUBLIC_KEY`를 권장합니다.

- 운영자는 배포 런타임과 분리된 안전한 환경에서 키와 토큰을 발급합니다.
  - `cd backend && python -m app.license_tokens generate-keypair --format env`
  - `LICENSE_PRIVATE_KEY`는 발급 환경의 secret으로만 보관하고 배포 환경에는 넣지 않습니다.
  - `LICENSE_PUBLIC_KEY`만 고객 배포 환경에 설정합니다.
- `LICENSE_PUBLIC_KEY`는 Ed25519 public key입니다. PEM 문자열 또는 base64url raw public key
  값을 사용할 수 있습니다.
- 고객에게 전달하는 `X-LICENSE-KEY` 값은 다음 형식의 offline token입니다.
  - `v1.<base64url-json-payload>.<base64url-ed25519-signature>`
- 토큰 발급/재발급 예시:
  - `cd backend && python -m app.license_tokens issue --private-key "$LICENSE_PRIVATE_KEY" --sub customer-acme --plan enterprise --jti license-2026-07 --exp 2027-07-02 --seats 25`
- signature 입력값은 `v1.<base64url-json-payload>` 문자열입니다.
- payload는 최소한 다음 claim을 포함해야 합니다.
  - `sub`: 고객/계약 식별자
  - `plan`: 계약 플랜 식별자
  - `exp`: Unix epoch seconds 만료 시각
- 선택 claim:
  - `jti`: 라이선스 토큰 식별자. 토큰 단위 회수와 재발급 추적에 사용합니다.
  - `nbf`: Unix epoch seconds 활성 시작 시각
  - `seats`: 양의 정수 시트 수
- `sub`, `plan`, `jti`는 앞뒤 공백이 없는 문자열이어야 합니다.
- 토큰 회수는 운영 환경 변수로 즉시 적용할 수 있습니다.
  - `LICENSE_REVOKED_TOKEN_IDS`: 쉼표로 구분한 회수 대상 `jti`
  - `LICENSE_REVOKED_SUBJECTS`: 쉼표로 구분한 회수 대상 `sub`
- 회수된 `jti` 또는 `sub`는 만료 전이라도 403으로 거절됩니다.
- 만료, 미활성, 잘못된 payload, 서명 변조는 각각 403으로 거절되며 관측 로그의
  `reason`/`X-Error-Code`에 반영됩니다.

## 4) 결제/과금 연계 전제

- 현재 단계는 상용화 준비 상태이며, 외부 결제 provider별 fulfillment SDK는 아직
  제품 내부에 고정하지 않습니다. 대신 공통 usage 조회, checkout/plan-change
  handoff, provider-neutral reconciliation event 기록 경로를 제공합니다.
- `GET /api/billing/usage`는 현재 사용자 소유 프로젝트 범위의 과금 준비용 사용량을
  반환합니다.
  - `project_count`
  - `seat_count`
  - `connection_count`
  - `snapshot_count`
  - `share_link_count`
  - `active_share_link_count`
  - `license_mode`, `license_verifier`
  - `project_limit`, `connection_limit`, `snapshot_limit`, `share_link_limit`
  - `account_status`
  - `billing_portal_url`, `billing_support_url`, `account_reactivation_url`
- live LLM draft 비용 폭주는 `LLM_DRAFT_QUOTA_ENABLED`,
  `LLM_DRAFT_QUOTA_REQUESTS`, `LLM_DRAFT_QUOTA_WINDOW_SECONDS`로 provider 호출 전
  차단합니다. 이 quota는 운영 비용 방어선이며, 월간 과금 attribution 또는 provider
  invoice 정산을 대체하지 않습니다.
- `POST /api/billing/checkout`은 `{ "target_plan": "enterprise-plus" }`
  요청을 받아 결제 시작 경로를 반환합니다.
  - `BILLING_CHECKOUT_URL`이 있으면 `target_plan` query를 붙인 checkout redirect
    action을 반환합니다.
  - checkout URL이 없고 `BILLING_SUPPORT_URL`이 있으면 support contact action을
    반환합니다.
  - 둘 다 없으면 `503`으로 실패해 판매 배포의 구매 시작 경로 누락을 드러냅니다.
  - 이 경로는 provider-specific fulfillment 완료, 영수증 처리, seat provisioning,
    invoice reconciliation을 대체하지 않습니다.
- `POST /api/billing/plan-change`는 `{ "target_plan": "enterprise-plus" }`
  요청을 받아 plan 변경 실행 경로를 반환합니다.
  - `BILLING_PORTAL_URL`이 있으면 `target_plan` query를 붙인 portal redirect
    action을 반환합니다.
  - portal이 없고 `BILLING_SUPPORT_URL`이 있으면 support contact action을 반환합니다.
  - 둘 다 없으면 `503`으로 실패해 판매 배포의 과금 경로 누락을 드러냅니다.
  - 사용자 subject 같은 식별자는 portal URL에 자동으로 넣지 않습니다. 고객 매핑은
    결제 포털 또는 계약 시스템에서 처리해야 합니다.
- `POST /api/billing/events`는 외부 결제/계약 시스템이 보낸 provider-neutral event를
  저장해 지원/정산 reconciliation 증거로 남깁니다.
  - `X-BILLING-WEBHOOK-SECRET` 헤더가 `BILLING_WEBHOOK_SECRET`과 일치해야 합니다.
  - `BILLING_WEBHOOK_SIGNATURE_SECRET`을 설정하면 raw request body의
    HMAC-SHA256 값도 `X-BILLING-WEBHOOK-SIGNATURE` 헤더로 검증합니다.
    헤더 값은 `sha256=<hex>` 또는 `<hex>` 형식을 허용합니다.
  - `BILLING_WEBHOOK_SECRET`과 `BILLING_WEBHOOK_SIGNATURE_SECRET`을 모두 설정한
    배포에서는 두 검증을 모두 통과해야 합니다.
  - `provider`와 `provider_event_id` 조합은 한 번만 기록됩니다. 동일 event가 다시
    오면 duplicate로 응답하고 상태를 두 번 적용하지 않습니다.
  - payload는 `provider`, `provider_event_id`, `event_type`, `subject`,
    `target_plan`, `occurred_at`, `metadata`를 받을 수 있습니다.
  - `BILLING_CONTRACT_STATE_EVENTS_ENABLED=true`이면 normalized `event_type`이
    `BILLING_CONTRACT_DEACTIVATED_EVENT_TYPES`에 포함될 때 해당 subject의 API
    접근을 `account deactivated`로 차단합니다. 이후 최신 contract-state event가
    `BILLING_CONTRACT_ACTIVE_EVENT_TYPES`에 포함되면 차단을 해제합니다.
  - 이 기능은 provider-specific checkout/fulfillment SDK가 아닙니다. Stripe,
    Paddle, 수기 계약 시스템 등 외부 provider의 원본 event는 gateway에서
    `contract.suspended`, `contract.reactivated` 같은 normalized event_type으로
    변환한 뒤 전송하거나, `BILLING_EVENT_TYPE_ALIASES` 운영값으로 서버 저장 전에
    정규화합니다.
  - `metadata`의 `secret`, `token`, `password`, `api_key`, `client_secret`,
    `authorization`, `card`, `dsn` 계열 키는 저장 전에 `[redacted]`로 치환됩니다.
  - 응답에는 민감 metadata를 반환하지 않습니다.
- `GET /api/billing/support/account?subject=<OIDC-subject>`는
  `SUPPORT_OPERATOR_SUBJECTS`에 포함된 사용자만 접근할 수 있는 read-only 지원
  진단 API입니다.
  - 대상 계정 UUID, 활성/비활성/미확인 상태, usage counter, license verifier,
    billing/reactivation URL, 최근 share link summary, 최근 billing event summary를
    반환합니다.
  - share link summary는 UUID, project UUID, 권한, 활성/만료 상태, 생성/만료
    시각만 포함하며 공개 URL/token은 반환하지 않습니다.
  - billing event의 raw metadata는 반환하지 않습니다.
  - allowlist에 없는 사용자는 `403 support operator role required`로 거절됩니다.
- `/api/me`는 현재 사용자가 `SUPPORT_OPERATOR_SUBJECTS`에 포함되어 있으면
  `support_operator: true`를 반환합니다. 프론트엔드는 이 값으로 `지원 진단`
  화면 노출 여부를 결정하지만, 실제 접근 제어는 항상 backend support API의
  allowlist 검증을 따릅니다.
- 유료 플랜 한도는 환경 변수로 적용합니다. 값이 `0`이면 해당 항목은 무제한입니다.
  - `BILLING_MAX_PROJECTS_PER_USER`
  - `BILLING_MAX_CONNECTIONS_PER_PROJECT`
  - `BILLING_MAX_SNAPSHOTS_PER_PROJECT`
  - `BILLING_MAX_SHARE_LINKS_PER_PROJECT`
- 결제 시작, 고객 포털 또는 지원 경로는 환경 변수로 노출합니다.
  - `BILLING_CHECKOUT_URL`: 신규 구매 또는 유료 전환 checkout 시작 URL
  - `BILLING_PORTAL_URL`: 플랜 변경, 결제수단, 청구 내역 관리 포털
  - `BILLING_SUPPORT_URL`: 결제/계약 문의 지원 경로
  - `BILLING_WEBHOOK_SECRET`: provider-neutral billing event 기록용 shared secret
  - `BILLING_WEBHOOK_SIGNATURE_SECRET`: provider/gateway webhook raw-body
    HMAC-SHA256 signature 검증용 secret
  - `BILLING_ALLOWED_PLANS`: plan-change 요청과 billing webhook `target_plan`을
    provider/customer catalog와 대조하는 쉼표 구분 plan ID 목록. 비어 있으면
    호환성을 위해 catalog 검증을 비활성화합니다.
  - `BILLING_EVENT_TYPE_ALIASES`: provider 원본 event_type을 내부 normalized
    event_type으로 바꾸는 쉼표 구분 `source=target` 목록. 공급자 충돌을 피하려면
    `stripe:customer.subscription.deleted=contract.suspended`처럼
    `provider:event_type=normalized_event_type` 형식을 사용합니다.
  - `BILLING_CONTRACT_STATE_EVENTS_ENABLED`: billing event에서 account
    deactivation/reactivation 상태를 적용할지 여부
  - `BILLING_CONTRACT_DEACTIVATED_EVENT_TYPES`: 접근 차단으로 해석할 normalized
    event_type 목록
  - `BILLING_CONTRACT_ACTIVE_EVENT_TYPES`: 접근 허용으로 복귀시키는 normalized
    event_type 목록
  - `ACCOUNT_REACTIVATION_URL`: 미납/계약 중단/abuse hold 해제 요청 경로
  - `SUPPORT_OPERATOR_SUBJECTS`: read-only 지원 진단 API 접근 허용 subject 목록
- 계약 중단, 미납, abuse 대응으로 계정 접근을 즉시 차단해야 하면
  `ACCOUNT_DEACTIVATED_SUBJECTS`에 OIDC subject를 쉼표로 구분해 설정합니다.
  해당 subject는 DB 사용자 upsert 전에 403으로 거절됩니다. 응답에는
  `X-Account-Status: deactivated`와, 설정된 경우 `X-Account-Reactivation-Url`,
  `X-Billing-Support-Url` 헤더가 포함됩니다.
- `APP_ENV=production`에서 `ACCOUNT_DEACTIVATED_SUBJECTS`를 설정하려면
  `ACCOUNT_REACTIVATION_URL` 또는 `BILLING_SUPPORT_URL` 중 하나가 필요합니다.
- `BILLING_EVENT_TYPE_ALIASES`가 적용되면 저장되는 `event_type`은 normalized
  값이 되며, 원본 provider event_type은 billing metadata의 `raw_event_type`에
  감사용으로 보존됩니다. Provider가 같은 key를 metadata로 보낸 경우에도 서버가
  실제 원본 event_type으로 덮어씁니다.
- `BILLING_ALLOWED_PLANS`가 설정된 경우 `POST /api/billing/checkout`,
  `POST /api/billing/plan-change`, `POST /api/billing/events`의 `target_plan`이
  catalog에 없으면 `422 target plan is not in configured billing catalog`로
  거절합니다. Billing webhook 거절은
  `billing_events_total{outcome="rejected_catalog"}`로 기록됩니다.
- 운영 전에는 다음 항목을 추가해야 합니다.
  - 계약 단위 플랜(월 구독/온프레미스 라이선스) 매핑
  - 청구 주기, 미납 정책, 계정 비활성 규칙
  - 팀별 시트/계정 할당량(사용자 수, API 호출량) 정책
  - provider별 fulfillment 어댑터, customer portal 심화 연동, 실제 event catalog에
    맞춘 별칭 및 plan catalog 운영값

## 5) 온프레미스 체크리스트

- `LICENSE_MODE=required`를 활성화하면 비인가 배포/임시 실행을 줄일 수 있습니다.
- 실제 영업용 패키지는 현재 CLI 기반 발급/재발급, 배포 환경 변수 기반 회수 목록,
  기본 사용량 한도, OIDC subject 기반 계정 비활성화를 사용할 수 있습니다. 다만 고객
  포털 기반 발급·회수·재발급 자동화와 자동 재활성화 정책은 별도 운영 시스템이
  필요합니다. 정적 `LICENSE_KEY`는 기존 배포 호환용으로만 유지합니다.
- 상업 전환 시에는 계정 포털(키 발급/회수/재발급/로그 감사)과 연동하세요.

## 6) 배포 체크포인트

- `LICENSE_MODE`와 `LICENSE_KEY` 또는 `LICENSE_PUBLIC_KEY`를 배포값으로 분리
- `LICENSE_REVOKED_TOKEN_IDS`, `LICENSE_REVOKED_SUBJECTS`를 비상 회수 절차에 포함
- 환경 변수 바인딩/문서화
- 운영 키 저장소(시크릿 저장소)에서만 관리
- 정적 키 노출 또는 서명 토큰 오남용 탐지 시 비상 대응(runbook) 연동
