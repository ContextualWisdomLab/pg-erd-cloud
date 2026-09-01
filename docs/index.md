# pg-erd-cloud

pg-erd-cloud는 PostgreSQL 중심의 클라우드 ERD 협업·공유 서비스입니다. 승인된 데이터베이스 연결에서 스키마를 역설계해 스냅샷으로 보존하고, 관계를 시각적으로 탐색하며, 검토 가능한 DDL·다이어그램·명세 산출물과 제한된 공유 흐름을 제공합니다.

> 이 페이지는 보호된 `main`의 현재 제품 경계를 기준으로 합니다. 활성 PR, 대기 중인 검증, 계획된 Forward Engineering 기능, 아직 발행되지 않은 릴리스나 Pages 배포를 이미 제공되는 기능처럼 표시하지 않습니다.

## 시작하기

- [저장소 개요와 로컬/프로덕션 실행 가이드](https://github.com/ContextualWisdomLab/pg-erd-cloud#readme)
- [API 보안 체크리스트](api-security-checklist.md)
- [관측성](observability.md)
- [Clearfolio 통합](clearfolio-integration.md)
- [LLM 오케스트레이터 통합](llm-orchestrator-integration.md)
- [응답 보안 헤더](response-security-headers.md)
- [CI 드리프트 검증](ci-drift-check.md)
- [Azure VMSS 상태 프로브](azure-vmss-health-extension.md)
- [보안 문서](security/codeql-sast-backfill.html)
- [UI/UX 문서](ui-ux/README.html)
- [Doctoring 기록](doctoring/search-identity-and-sequential-polling.html)
- [GitHub 릴리스](https://github.com/ContextualWisdomLab/pg-erd-cloud/releases)
- [Ask DeepWiki](https://deepwiki.com/ContextualWisdomLab/pg-erd-cloud)

## 제품 책임

pg-erd-cloud는 데이터베이스 스키마를 읽고 구조화된 스냅샷과 ERD 작업물로 변환하는 제품 경계를 소유합니다. 현재 보호된 기본 브랜치의 고객 가치는 PostgreSQL 역설계, 메타데이터 기반 ERD 탐색, 스냅샷·diff·검토용 DDL/내보내기, 제한된 공유 및 관련 보안·운영 계약에 집중되어 있습니다. 선택적 데이터베이스·LLM·포트폴리오 연계는 각 명시된 어댑터 경계를 통해 추가되며, pg-erd-cloud가 그 외 시스템의 권위까지 흡수하지 않습니다.

대상 데이터베이스의 운영 권한, 고객 인프라, ID 공급자, 비밀 수명주기, 외부 LLM 정책은 각각의 소유 경계에 남습니다. 특히 생성된 migration SQL이나 dry-run 기초가 존재한다는 사실만으로 프로덕션 데이터베이스에 대한 승인·적용·복구 권한이 완성되었다고 보지 않습니다.

## 현재 워크플로

승인된 사용자는 프로젝트와 데이터베이스 연결을 구성하고 비동기 스냅샷 작업을 실행합니다. 성공한 스냅샷은 스키마·테이블·컬럼·키·인덱스와 같은 구조 메타데이터의 검토 가능한 시점을 만들며, 프론트엔드는 이를 관계 그래프로 탐색하고 검색·레이아웃·내보내기 흐름에 사용합니다. 공개 공유 export는 민감한 코멘트와 예시 값을 redaction하지만, 현재 `llm-draft` 모드는 외부 provider 호출을 유발할 수 있으므로 공개 링크 자체를 비용·권한 경계로 간주해서는 안 됩니다.

## 검증과 릴리스 경계

릴리스 수용 여부는 그 시점의 보호된 `main`에 실제로 구성된 required workflow, 보안 검사, 리뷰 및 브랜치 보호 증거로 판단합니다. 특정 coverage·dependency·SBOM 검사가 문서에 언급되었다는 이유만으로 해당 검사가 현재 required gate라고 추정하지 않습니다. 이전 head의 성공, queued/skipped 상태, 모델 전용 리뷰, 활성 PR의 문서 문구는 릴리스 증거로 승격하지 않습니다. 이 저장소에는 현재 GitHub Release가 없으므로 릴리스 링크는 향후 검증된 아티팩트가 게시될 위치를 가리킬 뿐입니다.

## Pages 발행 경계

`docs/index.md`가 존재하는 것만으로 GitHub Pages가 발행된 것은 아닙니다. 보호된 브랜치 통합, 조직 소유 설정/배포 경로의 성공, 그리고 실제 HTTPS 사이트의 내용 검증까지 완료되어야 Pages가 라이브라고 간주합니다.

## 라이선스

pg-erd-cloud 소스는 [Apache License 2.0](https://github.com/ContextualWisdomLab/pg-erd-cloud/blob/main/LICENSE)으로 제공됩니다. 제3자 의존성은 각자의 라이선스 조건을 유지합니다.
