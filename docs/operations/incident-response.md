# Incident Response Runbook

이 문서는 `pg-erd-cloud` 운영 중 긴급 장애가 발생했을 때 1차 대응 순서를 정의합니다.

## Severity 정의

- **S1: 고객 데이터 또는 계정 접근 손실 위험**
  - 공개 공유 링크가 대량 유출되거나, 권한 우회가 확인된 경우
  - 공유 링크/프로젝트 데이터 손실 또는 잘못된 데이터 노출이 의심되는 경우
- **S2: 서비스 이용 장애**
  - 백엔드 API 다수 응답 실패(5xx 급증), 중요 엔드포인트 `/healthz` 실패
  - 스냅샷 생성/조회 전반이 중단되는 경우
- **S3: 성능 및 비용 이상**
  - LLM draft 비용 급등 의심, 요청 폭주로 인한 과금/성능 임계치 초과

## 5분 진입 체크리스트 (SRE On-call)

1. 상태 확인
   - `/healthz` 응답, 최근 배포 상태, 알림 채널 알람 수신 내역 확인
   - 앱 로그에서 `event=share_audit`의 `request_id`를 기준으로 `event=authz_failure`, `http_request`와 함께 조회
   - `authz_failures_total` 및 `share_audit_events_total` 메트릭에서 직전 15분 구간의 급증 여부를 우선 점검
2. 스코프 확인
   - 공개 공유 링크 계열인지, 인증 API인지, LLM draft 경로인지 분기
3. 피해 억제
   - 긴급 차단이 필요한 경우 `APP_ENV`가 아니더라도 라우팅/방화벽에서
     `mode=llm-draft` 경로를 일시 제한
   - 필요 시 공유 링크 목록 폐기 API를 통해 이상 링크 즉시 폐기
4. 커뮤니케이션
   - 장애 원인 추정과 임시 완화 조치, 예상 복구 ETA를 내부 채널에 공유

## LLM 비용 과다 사용 대응

- 첫 단계: `SHARE_LINK_LLM_DRAFT_ENABLED=false` 또는 `app.share` 감시 알람 기준으로
  공유 링크 draft 경로를 임시 비활성화
- 두 번째 단계: LLM provider key 회전 및 토큰 예산 제한 재점검
- 세 번째 단계: 과금 추적 로그를 기준으로 상위 요청자/공유 링크 UUID를 식별 후
  해당 공유 자격 폐기

## 운영 로그 및 근거 보존

- 장애 대응 중 다음 항목은 보존합니다.
  - 로그: `app.share`, `app.main`, 배포 이벤트, 백엔드 에러 로그
  - 배포/마이그레이션 이력: `git log`, `alembic current`
  - 영향 범위: 장애 기간, 사용자 영향, 실패 API 목록, 조치 시간

## 복구 후 정리

1. `alembic current`/`alembic history`를 통해 스키마 정합성 확인
2. 핵심 API smoke test(`/healthz`, 스냅샷 조회, 공유 링크 조회/폐기, SQL export) 실행
3. 장애 대응 절차와 원인, 조치 근거를 운영 로그/이슈에 남김
4. 같은 유형이 30일 내 반복되면 `docs/commercial-readiness.md` P1 항목
   (알람 정책/한계치) 업데이트
