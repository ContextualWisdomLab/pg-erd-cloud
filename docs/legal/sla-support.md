# SLA / 지원 운영 기준

본 문서는 상용 출시 전 지원 운영 기준입니다. 계약별 응답 시간, 크레딧,
위약/면책 문구는 `commercial-release-approval.md`의 승인 기록에 연결합니다.

## 가용성

- 기본 목표: 평일 업무 시간 내 장애 대응 체계를 갖춘 운영
- 24x7 무중단 SLO를 제공하려면 모니터링, 알림 채널, 장애 대응 교대조 체계를 별도 운영해야 합니다.

## 지원 채널

- 1차: 저장소 이슈 트래커 또는 계약 채널
- 긴급: 내부 핫라인(운영 runbook 연동)
- 응답 기준: 계약 등급별로 분류
- 보안 취약점: `SECURITY.md`의 private advisory 경로 사용

## 장애 대응

- 알림: `rate limit`, `share_audit`, `LLM provider` 실패, 인증 실패 급증
- 대응 문서: `docs/operations/incident-response.md`
- 백업/복구: `docs/operations/backup-restore.md`
- 마이그레이션 롤백: `docs/operations/migration-rollback.md`

## 데이터 보전

- 규정된 보존 기간 이후 로그/스냅샷 정리 정책
- 백업 복구 연습은 월 1회 이상 권장

## 판매 전 승인 조건

- 계약 등급별 응답 목표와 제외 범위를 계약서에 반영
- 지원 채널, 담당자, 긴급 연락 경로 확정
- 장애 통지 기준과 고객 공지 템플릿 확정
- 백업/복구 및 마이그레이션 롤백 runbook 리허설 완료
