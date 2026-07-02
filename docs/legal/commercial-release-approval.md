# 상용 릴리즈 법무/지원 승인 체크리스트

이 문서는 pg-erd-cloud를 유료 SaaS 또는 온프레미스 패키지로 판매하기 전에
릴리즈 책임자가 확인해야 하는 승인 gate입니다. 법률 자문을 대체하지 않으며,
승인 기록이 없으면 일반 판매를 진행하지 않습니다.

## 1) 필수 승인 산출물

- 이용약관: `docs/legal/terms-of-service.md`
- 개인정보 처리 안내: `docs/legal/privacy-policy.md`
- SLA/지원 기준: `docs/legal/sla-support.md`
- 라이선스/결제 운영 기준: `docs/legal/license-billing.md`
- 보안 취약점 신고 정책: `SECURITY.md`
- 운영 runbook:
  - `docs/operations/incident-response.md`
  - `docs/operations/backup-restore.md`
  - `docs/operations/migration-rollback.md`
  - `docs/operations/on-premises-package.md`
  - `docs/operations/alert-thresholds.md`

## 2) 판매 전 필수 결정

- 판매 형태: SaaS, 온프레미스, 또는 하이브리드
- 계약 플랜: 평가판, 유료 베타, 일반 판매, 엔터프라이즈
- 결제 방식: 수동 인보이스, 외부 결제 대행, 또는 리셀러 계약
- 데이터 처리 범위: 앱 메타데이터, 접속 DSN, 스냅샷 JSON, 감사 로그, 지원 로그
- 보존 기간: 프로젝트/스냅샷/공유 링크/감사 로그/백업별 보존 기간
- 지원 채널: 계약 이메일, 티켓 시스템, 보안 advisory, 긴급 연락 경로
- 취약점 대응 소유자: 접수, triage, 패치, 고객 통보 책임자
- 하위 처리자: 결제, 분석, 고객지원, 호스팅, LLM provider 사용 여부

## 3) 승인 기록

릴리즈 전 다음 항목을 릴리즈 이슈 또는 계약 승인 문서에 남깁니다.
판매 대상 릴리즈를 저장소에 기록할 때는
`docs/legal/release-approvals/release-approval.example.json`을 복사해
릴리즈별 manifest를 만들고, `scripts/ci/validate_commercial_release_approval.py`가
CI에서 통과해야 합니다. example 파일은 형식 검증용이며 실제 승인 기록으로
간주하지 않습니다.

| 항목 | 값 |
|---|---|
| 릴리즈 버전/커밋 |  |
| 판매 형태 |  |
| 승인 일자 |  |
| 제품 책임자 |  |
| 법무/계약 승인자 |  |
| 보안 승인자 |  |
| 지원 운영 승인자 |  |
| 적용 약관/개인정보/SLA 문서 버전 |  |
| 알려진 미지원 범위 |  |
| 고객 통지 필요 사항 |  |

## 4) No-Go 조건

다음 중 하나라도 해당하면 일반 판매를 보류합니다.

- 승인 기록이 없거나 승인자가 비어 있음
- 개인정보 처리 안내가 실제 배포의 제3자 처리자와 맞지 않음
- SLA/지원 기준에 응답 시간, 제외 범위, 긴급 연락 경로가 없음
- 라이선스 발급/회수 절차와 고객 계약 조건이 불일치함
- 보안 취약점 신고 경로 또는 triage 책임자가 없음
- 운영 runbook 없이 데이터 복구, 배포 롤백, 장애 통지가 필요한 계약을 판매함
