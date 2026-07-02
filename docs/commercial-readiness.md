# Commercial Readiness Plan

이 문서는 `pg-erd-cloud`를 판매 가능한 SaaS 또는 온프레미스 제공물로 만들기 위한
구체 기준과 현재 결론을 정리합니다. 자동 리뷰 봇이나 장시간 분석 봇의 지연은
출시 blocker로 보지 않고, 보안/비용/데이터/운영/법무/지원 관점의 실제 결함만
blocker로 분류합니다.

## Current Verdict

현재 제품은 실행 가능한 MVP 기반이지만, 그대로 판매 가능한 프로그램은 아닙니다.
핵심 이유는 README 자체가 MVP로 표기되어 있고, 공개 공유 링크/LLM 비용 통제,
공유 링크 수명주기, 프로덕션 설정 강제, 백업/복구, 법무/지원 문서, 과금/사용량
한도, 운영 알림 기준이 상용 패키지 수준으로 닫혀 있지 않기 때문입니다.

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

### P1: 유료 베타 필수

- 공유 링크별 감사 로그를 제공해야 합니다.
- 프로덕션 설정 guard를 추가해 약한 `APP_SECRET`, localhost-only CORS, OIDC 누락,
  target DB allowlist 누락을 조기 탐지해야 합니다.
- 백업/복구 runbook, migration rollback policy, 장애 대응 runbook을 문서화해야 합니다.
- LLM draft 사용량/비용 한도, provider timeout, 실패율 알림 기준을 운영 문서와
  테스트로 고정해야 합니다.
- 설치/운영 문서에서 MVP 표현을 제거하고, 지원 범위와 미지원 범위를 명시해야 합니다.

### P2: 일반 판매 권장

- 결제/라이선스/좌석 관리 또는 온프레미스 license key 검증 경로를 제공해야 합니다.
- SLA, 지원 채널, 보안 취약점 처리 정책, 개인정보 처리 문서, 약관을 배포물에 포함해야 합니다.
- 시각 회귀 테스트, 브라우저 E2E, 접근성 스모크 테스트를 CI release gate로 운영해야 합니다.
- 관리자가 프로젝트/멤버/공유 링크/사용량을 검색하고 제한할 수 있어야 합니다.

## First Implementation Slice

이번 1차 구현은 판매 전 P0 중 “공개 엔드포인트 비용/노출 남용 방지”를 닫습니다.

- `SHARE_LINK_LLM_DRAFT_ENABLED=false`를 기본값으로 추가합니다.
- 공개 공유 링크의 `mode=llm-draft` 호출은 기본적으로 `403`으로 차단합니다.
- 인증된 snapshot API의 live LLM draft는 기존 동작을 유지합니다.
- `SHARE_LINK_DEFAULT_TTL_HOURS=168`을 기본값으로 추가해 공개 공유 링크를 7일 뒤
  만료시킵니다.
- 프로젝트 오너가 공유 링크를 목록 조회하고 삭제 방식으로 폐기할 수 있게 합니다.
- 운영자가 공개 공유 링크 LLM draft를 의도적으로 열 수는 있지만, 별도 비용 한도,
  감사 로그, 운영 승인 정책을 갖춘 배포에서만 사용하도록 문서화합니다.

## Ongoing Execution Rules

- 리뷰 봇 대기, 장시간 정적 분석 대기, 비필수 자동화 지연은 blocker가 아닙니다.
- blocker는 고객 데이터 노출, 비용 무제한 발생, 인증/인가 우회, 배포 불능, 핵심
  검증 실패, 법무/지원 문서 부재처럼 판매 가능성을 직접 막는 항목입니다.
- 각 반복은 하나 이상의 blocker 또는 P1 gap을 코드/문서/테스트로 닫고 PR에 남깁니다.
