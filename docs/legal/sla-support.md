# SLA / 지원 운영준비(초안)

본 문서는 상용 출시 전 점검용으로, 판매 전 실제 SLA 문구로 교체해야 합니다.

## 가용성

- 기본 목표: 평일 업무 시간 내 장애 대응 체계를 갖춘 운영
- 24x7 무중단 SLO를 제공하려면 모니터링, 알림 채널, 장애 대응 교대조 체계를 별도 운영해야 합니다.

## 지원 채널

- 1차: 저장소 이슈 트래커 또는 계약 채널
- 긴급: 내부 핫라인(운영 runbook 연동)
- 응답 기준: 계약 등급별로 분류

## 장애 대응

- 알림: `rate limit`, `share_audit`, `LLM provider` 실패, 인증 실패 급증
- 대응 문서: `docs/operations/incident-response.md`
- 백업/복구: `docs/operations/backup-restore.md`
- 마이그레이션 롤백: `docs/operations/migration-rollback.md`

## 데이터 보전

- 규정된 보존 기간 이후 로그/스냅샷 정리 정책
- 백업 복구 연습은 월 1회 이상 권장
