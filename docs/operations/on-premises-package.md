# On-Premises Package Checklist

이 문서는 `pg-erd-cloud`를 고객 관리 환경에 설치하거나 평가 배포할 때 필요한
상용 패키지 점검표입니다. SaaS 운영 문서와 달리, 네트워크가 제한된 고객 환경과
운영자 인수인계를 기준으로 작성합니다.

## Package Boundary

패키지 기준 파일:

- `compose.prod.yaml`
- `.env.example`
- `backend/Dockerfile`
- `frontend/Dockerfile.prod`
- `deploy/traefik/dynamic.yaml`
- `docs/legal/license-billing.md`
- `docs/operations/backup-restore.md`
- `docs/operations/restore-drills/restore-drill.example.json`
- `docs/operations/migration-rollback.md`
- `docs/operations/incident-response.md`
- `docs/operations/alert-thresholds.md`

`scripts/ci/validate_onprem_package.py`는 위 파일과 필수 문구를 정적으로 검사합니다.
`scripts/ci/validate_restore_drill_manifest.py`는 restore drill evidence manifest의
필수 smoke 결과와 secret redaction 기준을 검사합니다.

## Offline license

- 운영자는 배포 환경 밖에서 Ed25519 keypair를 생성합니다.
  - `cd backend && python -m app.license_tokens generate-keypair --format env`
- 배포 환경에는 `LICENSE_PUBLIC_KEY`만 설정합니다.
- 고객에게 전달하는 `X-LICENSE-KEY`는 signed offline token입니다.
  - `cd backend && python -m app.license_tokens issue --private-key "$LICENSE_PRIVATE_KEY" --sub customer-acme --plan enterprise --jti license-2026-07 --exp 2027-07-02 --seats 25`
- `LICENSE_MODE=required`를 켠 판매 배포는 `LICENSE_KEY` 또는
  `LICENSE_PUBLIC_KEY` 중 하나가 없으면 시작하지 않아야 합니다.

## Secret material

- `APP_SECRET`은 앱 DB 백업과 분리 보관합니다.
- compose production path는 `APP_SECRET_FILE=/run/secrets/app_secret`을 사용하고,
  secret file은 `./secrets/app_secret`에서 읽습니다.
- `APP_SECRET` 또는 secret file이 유실되면 저장된 DSN ciphertext를 복호화할 수
  없으므로 restore 완료로 보지 않습니다.
- `POSTGRES_PASSWORD`, `BILLING_WEBHOOK_SECRET`,
  `BILLING_WEBHOOK_SIGNATURE_SECRET`, provider secret, private license key는 저장소에
  커밋하지 않습니다. production에서는 billing webhook shared secret은 24자 이상,
  signature secret은 32자 이상이어야 합니다.

## Revocation update

- 토큰 단위 회수는 `LICENSE_REVOKED_TOKEN_IDS`로 배포합니다.
- 고객/계약 단위 회수는 `LICENSE_REVOKED_SUBJECTS`로 배포합니다.
- 계정 접근 중지는 `ACCOUNT_DEACTIVATED_SUBJECTS`로 배포하고,
  `ACCOUNT_REACTIVATION_URL` 또는 `BILLING_SUPPORT_URL` 중 하나를 함께 제공합니다.
- 지원 운영자 read-only 진단 접근은 `SUPPORT_OPERATOR_SUBJECTS`로 제한합니다.

## Air-gapped

- 고객 환경에서 외부 registry 접근이 막혀 있으면 container image를 사전 반입하고,
  `compose.prod.yaml`의 image digest 기준으로 무결성을 확인합니다.
- 짧은 수명 컨테이너로 내부 DB 또는 registry를 점검해야 하는 self-hosted runner에서는
  고객 DNS 정책에 따라 `docker run --network host ...`가 필요할 수 있습니다.
- live LLM draft는 승인된 provider와 네트워크 정책이 없으면 비활성 상태를 유지합니다.

## Restore drill

- 운영 투입 전 `docs/operations/backup-restore.md`의 restore drill을 최소 1회 수행합니다.
- restore DB는 운영 DB가 아닌 격리 PostgreSQL입니다.
- restore 후 `/healthz`, `alembic current`, 프로젝트 조회, 공유 링크 조회/폐기,
  SQL export smoke를 확인합니다.
- 결과는 릴리즈 승인 기록 또는 운영 이슈에 남기고,
  `docs/operations/restore-drills/restore-drill.example.json` 형식의 manifest로
  보존합니다.

## Rollback drill

- 운영 투입 전 `docs/operations/migration-rollback.md`의 dry-run 절차를 검토합니다.
- `alembic downgrade --sql <revision> -1`로 마지막 마이그레이션 rollback SQL을
  확인합니다.
- 실제 downgrade는 staging 또는 restore drill DB에서 먼저 수행합니다.
- rollback 후에도 문제가 남으면 restore drill 절차로 전환합니다.

## Support bundle

지원 요청을 받을 때 고객에게 요청할 최소 bundle:

- 배포 commit SHA
- `alembic current` 출력
- `compose.prod.yaml` 변경 여부
- `/healthz` 응답
- 최근 backend error log
- `GET /api/billing/support/account?subject=<OIDC-subject>` 결과에서 raw metadata와
  공개 share URL/token을 제외한 summary
- 적용 중인 `LICENSE_MODE`, verifier 종류, revocation env 이름 목록

민감값(`APP_SECRET`, DB password, DSN, private key, billing secret, raw provider
metadata)은 support bundle에 포함하지 않습니다.

## Release Gate

온프레미스 판매 후보는 다음을 모두 만족해야 합니다.

- `python scripts/ci/validate_onprem_package.py` 통과
- `python scripts/ci/validate_restore_drill_manifest.py` 통과
- `python scripts/ci/validate_commercial_release_approval.py` 통과
- backend tests, frontend unit/accessibility/E2E/visual/build 통과
- 실제 판매 버전의 release approval manifest에 설치/지원 책임자와 승인일 기재
