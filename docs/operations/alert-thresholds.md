# Commercial Alert Thresholds

이 문서는 `deploy/prometheus/pg-erd-cloud-alerts.yml`의 기본 alert rule을
상용 SaaS/온프레미스 운영 gate로 해석하는 기준입니다. 환경별 수치 조정은 가능하지만,
severity, 고객 영향 판단, 1차 조치, escalation owner는 릴리즈 승인 기록에 남겨야
합니다.

## Threshold Matrix

| Alert | Severity | Commercial threshold | Customer impact | First response | Owner |
|---|---|---|---|---|---|
| `PgErdCloudHigh5xxRate` | `page` | 5분 동안 전체 요청 중 5xx 비율 > 1% | API 생성/조회/공유 흐름 실패 가능 | 최근 배포, DB 연결, upstream 오류율 확인 후 incident commander 지정 | On-call engineer |
| `PgErdCloudHighRouteLatency` | `ticket` | 10분 동안 route별 p95 > 1s | ERD 조회, 공유 링크, 관리 화면 지연 | route label별 상위 지연 원인과 DB/queue 대기 확인 | Backend owner |
| `PgErdCloudAuthzFailureSpike` | `ticket` | route/reason별 5분 rate > 10/s | 인증 설정 drift, abuse, 고객 SSO 장애 가능 | OIDC issuer/audience drift, deactivated subject, rate limit 로그 확인 | Security owner |
| `PgErdCloudShareAbuseOrFailureSpike` | `ticket` | action/outcome별 denied/failed 5분 rate > 5/s | 공개 공유 링크 남용 또는 고객 공유 실패 | share audit 로그, request_id, link TTL/revocation 상태 확인 | Support + Security |
| `PgErdCloudBillingWebhookFailures` | `ticket` | 10분 동안 billing webhook rejected_auth/rejected_config/rejected_catalog > 0 | 결제/계약 event 반영 실패, 미납/플랜 변경 상태 불일치 가능 | provider/gateway secret, raw-body signature, `BILLING_ALLOWED_PLANS`, event replay, support diagnostics 확인 | Billing owner |
| `PgErdCloudLlmDraftFailures` | `ticket` | 10분 동안 LLM draft configuration/provider/prompt-size/quota 실패 > 0 | LLM 보조 산출물 생성 실패 또는 제3자 provider 비용/연동 문제 가능 | `event=llm_draft_usage`, provider key, prompt size, `SHARE_LINK_LLM_DRAFT_ENABLED`, `LLM_DRAFT_QUOTA_*` 상태 확인 | Product + Backend owner |
| `PgErdCloudJobFailures` | `ticket` | 10분 동안 background job 실패 > 0 | 스냅샷 생성/역공학 작업 실패 | 실패 job type, DSN allowlist, target DB reachability 확인 | Backend owner |
| `PgErdCloudJobQueueWaitHigh` | `ticket` | 10분 동안 job type별 p95 wait > 60s | 스냅샷 생성 대기 증가 | worker 수, DB lock, queue backlog, run_after drift 확인 | Operations owner |

## Escalation Rules

- `page` alert는 15분 안에 담당자를 지정하고 incident timeline을 시작합니다.
- 동일 고객 또는 동일 route에서 `ticket` alert가 30분 이상 지속되면 `page`로 승격합니다.
- authz/share abuse alert는 고객 영향이 없어도 보안 triage 기록을 남깁니다.
- LLM provider 또는 billing provider 장애가 연관되면 고객 공지 필요 여부를
  `docs/legal/release-approvals/*.json`의 `customer_notice` 정책과 비교합니다.

## Release Approval Checklist

상용 릴리즈 승인자는 다음을 확인합니다.

- Prometheus rule 파일이 배포 대상 환경에 로드되어 있습니다.
- `/metrics`는 내부망 또는 token-protected endpoint로 제한되어 있습니다.
- severity별 담당자와 escalation channel이 계약 지원 문서와 일치합니다.
- threshold를 환경별로 변경한 경우 변경 사유, 새 수치, 승인자를 manifest에 기록했습니다.
