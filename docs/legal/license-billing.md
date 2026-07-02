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

- 현재 단계는 상용화 준비 상태(POC)이며, 별도 과금 라우트(Billing, invoicing, seat API)는
  아직 미구현입니다.
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
- 유료 플랜 한도는 환경 변수로 적용합니다. 값이 `0`이면 해당 항목은 무제한입니다.
  - `BILLING_MAX_PROJECTS_PER_USER`
  - `BILLING_MAX_CONNECTIONS_PER_PROJECT`
  - `BILLING_MAX_SNAPSHOTS_PER_PROJECT`
  - `BILLING_MAX_SHARE_LINKS_PER_PROJECT`
- 고객 포털 또는 지원 경로는 환경 변수로 노출합니다.
  - `BILLING_PORTAL_URL`: 플랜 변경, 결제수단, 청구 내역 관리 포털
  - `BILLING_SUPPORT_URL`: 결제/계약 문의 지원 경로
  - `ACCOUNT_REACTIVATION_URL`: 미납/계약 중단/abuse hold 해제 요청 경로
- 계약 중단, 미납, abuse 대응으로 계정 접근을 즉시 차단해야 하면
  `ACCOUNT_DEACTIVATED_SUBJECTS`에 OIDC subject를 쉼표로 구분해 설정합니다.
  해당 subject는 DB 사용자 upsert 전에 403으로 거절됩니다. 응답에는
  `X-Account-Status: deactivated`와, 설정된 경우 `X-Account-Reactivation-Url`,
  `X-Billing-Support-Url` 헤더가 포함됩니다.
- `APP_ENV=production`에서 `ACCOUNT_DEACTIVATED_SUBJECTS`를 설정하려면
  `ACCOUNT_REACTIVATION_URL` 또는 `BILLING_SUPPORT_URL` 중 하나가 필요합니다.
- 운영 전에는 다음 항목을 추가해야 합니다.
  - 계약 단위 플랜(월 구독/온프레미스 라이선스) 매핑
  - 청구 주기, 미납 정책, 계정 비활성 규칙
  - 팀별 시트/계정 할당량(사용자 수, API 호출량) 정책
  - 위반 탐지 시 자동 비활성화/재활성화 실행 규칙

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
