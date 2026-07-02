# Commercial Readiness Plan

이 문서는 `pg-erd-cloud`를 판매 가능한 SaaS 또는 온프레미스 제공물로 만들기 위한
구체 기준과 현재 결론을 정리합니다. 자동 리뷰 봇이나 장시간 분석 봇의 지연은
출시 blocker로 보지 않고, 보안/비용/데이터/운영/법무/지원 관점의 실제 결함만
blocker로 분류합니다.

## Current Verdict

현재 제품은 실행 가능한 MVP 기반이지만, 그대로 판매 가능한 프로그램은 아닙니다.
핵심 이유는 보안/인증/운영 체계가 모두 완성 단계에 있지 않기 때문입니다.

### Current Control Board (2026-07-02 UTC)

- P0: `in_progress` (공개 비용 방지와 핵심 설정 강제는 완료했고, 인증 실패
  대응 메시지/알람 통일과 일부 운영 임계치 보강은 진행 중)
- P1: `in_progress` (공유 링크 감사 로그, migration rollback, 장애 대응 runbook은
  1차 진행 중)
- P2: `not_started` (결제/라이선스, 보안 운영 SLA, 법무 문서 체계 미구축)

## Release Gates

### P0: 판매 전 필수

- 인증: 운영 환경에서 OIDC issuer/audience/alg allowlist가 강제되고, 미설정 시
  명확히 실패해야 합니다.
- 인가: 프로젝트 멤버십, 오너 권한, 공유 링크 권한이 테스트로 보호되어야 합니다.
- 데이터 보호: 저장 DSN 암호화, secret 파일 주입, DSN/error redaction, 대상 DB
  allowlist가 기본 방어선으로 동작해야 합니다.
- 공개 엔드포인트 남용 방지: `/api/share/*`는 별도 rate limit과 기본 만료를 적용하고,
  외부 비용을 만들 수 있는 live LLM draft는 기본 차단해야 합니다.
- 배포 재현성: Docker/prod compose, backend/frontend lockfile, 런타임 버전이 일관되어야 합니다.
- 검증: backend mypy/pytest, frontend typecheck/test/build가 main 기준에서 통과해야 합니다.

현재 상태

- ✅ `SHARE_LINK_LLM_DRAFT_ENABLED=false` 기본값 및 공용 공유의 LLM 비용 방지
- ✅ `APP_ENV=production` startup guard로 핵심 보안 설정 강제
- ✅ `Llm` prompt/output 상한으로 비용 탐색 경로 제한
- ✅ `share 링크` TTL 기본값 7일(`SHARE_LINK_DEFAULT_TTL_HOURS=168`) 적용
- ✅ 인증 실패 응답(`authz_failure`) 관측 이벤트 로깅 추가
- 🟡 사용자 안내 메시지 표준화와 보안 알림 임계치 전략은 진행 중

### P1: 유료 베타 필수

- 공유 링크별 감사 로그를 제공해야 합니다.
- migration rollback policy와 장애 대응 runbook을 문서화해야 합니다.
- LLM draft 사용량 감사 로그와 실패율 알림 기준을 운영 문서와 테스트로 고정해야 합니다.
- 설치/운영 문서에서 MVP 표현을 제거하고, 지원 범위와 미지원 범위를 명시해야 합니다.

현재 상태

- ✅ 공유 링크 운영 감사 로그 JSON 이벤트(`event=share_audit`) 추가 및 경로별 테스트
- ✅ `docs/operations/backup-restore.md` 추가로 앱 DB 복구 절차 기초 정립
- ✅ `docs/operations/migration-rollback.md` 작성 및 운영 복구 문서화
- ✅ `docs/operations/incident-response.md` 작성 및 1차 대응 흐름 정리
- 🟡 운영 알림(LLM 비용/오류율, 공유 링크 남용) 임계치 정책 문서·구성 미완

### P2: 일반 판매 권장

- 결제/라이선스/좌석 관리 또는 온프레미스 license key 검증 경로를 제공해야 합니다.
- SLA, 지원 채널, 보안 취약점 처리 정책, 개인정보 처리 문서, 약관을 배포물에 포함해야 합니다.
- 시각 회귀 테스트, 브라우저 E2E, 접근성 스모크 테스트를 CI release gate로 운영해야 합니다.
- 관리자가 프로젝트/멤버/공유 링크/사용량을 검색하고 제한할 수 있어야 합니다.

현재 상태

- 🟡 결제/라이선스/좌석/미터링은 계획 단계 미입력
- 🟡 법무 문서(개인정보 처리, 이용약관, 면책/보증)는 미구축
- 🟡 고급 운영 테스트(E2E/회귀/접근성) CI 연동은 미완

## First Implementation Slice

이번 2차 반복 구현은 P0의 “공개 엔드포인트 비용/노출 남용 방지”와 P1의
공유 링크 감사 추적을 닫는 작업을 함께 진행합니다.

- `SHARE_LINK_LLM_DRAFT_ENABLED=false`를 기본값으로 추가합니다.
- 공개 공유 링크의 `mode=llm-draft` 호출은 기본적으로 `403`으로 차단합니다.
- 인증된 snapshot API의 live LLM draft는 기존 동작을 유지합니다.
- `SHARE_LINK_DEFAULT_TTL_HOURS=168`을 기본값으로 추가해 공개 공유 링크를 7일 뒤
  만료시킵니다.
- 프로젝트 오너가 공유 링크를 목록 조회하고 삭제 방식으로 폐기할 수 있게 합니다.
- `APP_ENV=production` startup guard로 OIDC, 공개 HTTPS CORS origin, 강한 secret,
  대상 DB allowlist, 공유 링크 기본 만료를 강제합니다.
- 인증된 live LLM draft도 `LLM_MAX_PROMPT_CHARS`와 `LLM_MAX_OUTPUT_TOKENS`로
  provider 호출 전 비용 상한을 둡니다.
- 앱 메타데이터 PostgreSQL backup/restore runbook을 추가합니다.
- 운영자가 공개 공유 링크 LLM draft를 의도적으로 열 수는 있지만, 별도 비용 한도,
  감사 로그, 운영 승인 정책을 갖춘 배포에서만 사용하도록 문서화합니다.
- 공개 공유 링크 감사 로그는 모든 성공/실패 동작에서 JSON 이벤트로 기록되며,
  실시간 모니터링 연계 시 사용 가능한 형태로 유지합니다.

## Ongoing Execution Rules

- 리뷰 봇 대기, 장시간 정적 분석 대기, 비필수 자동화 지연은 blocker가 아닙니다.
- blocker는 고객 데이터 노출, 비용 무제한 발생, 인증/인가 우회, 배포 불능, 핵심
  검증 실패, 법무/지원 문서 부재처럼 판매 가능성을 직접 막는 항목입니다.
- 각 반복은 하나 이상의 blocker 또는 P1 gap을 코드/문서/테스트로 닫고 PR에 남깁니다.
