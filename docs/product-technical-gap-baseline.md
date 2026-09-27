# Product and Technical Gap Baseline

- 상태: 활성 PR 증거이며 protected `main` 또는 릴리스 주장 아님
- 스냅샷 날짜: 2026-09-27 (Asia/Seoul)
- 평가한 protected-main head: `8dc746920c12988f082e914879d95e13c9693535`
- 활성 PR: [#971](https://github.com/ContextualWisdomLab/pg-erd-cloud/pull/971)
- 실패한 exact head: `9b571e3688507aa9099cb82e592b2ecc8974b346`

## Exact-head RCA

[`frontend` job `97240084749`](https://github.com/ContextualWisdomLab/pg-erd-cloud/actions/runs/32658154398/job/97240084749)은 201개 테스트 중 199개를 통과하고 `src/App.coverage.test.tsx`의 두 비동기 화면 전환에서 실패했다. 첫 경로는 다이어그램 검색 입력 직후 `검색 결과가 없습니다.`를 동기 조회했고, 두 번째 경로는 다이어그램 목록 효과가 끝나기 전에 `열기` 버튼을 동기 조회했다. 두 UI 요소는 실제 제품 컴포넌트에 존재하며 동일 exact head의 전체 suite와 해당 파일 반복 8회는 로컬에서 통과했다. 이는 제품 기능 부재가 아니라 hosted runner 처리 속도에 노출된 fixture race다.

최소 수정은 제품 코드, 접근성 이름, timeout, coverage 또는 gate를 변경하지 않는다. 기존 Testing Library 비동기 쿼리 패턴과 동일하게 검색 빈 상태는 `findByText`로 기다리고, 다이어그램 버튼은 real timers에서 `findAllByRole`로 확보한 뒤 polling 검증용 fake timers로 전환한다.

## Gap 및 조치 상태

| 우선순위 | Gap | 조치 | 완료 증거 | 상태 |
|---|---|---|---|---|
| P0 | hosted frontend gate가 비동기 effect보다 먼저 동기 assertion을 실행해 dependency-only PR도 실패시킨다. | 두 실제 렌더 결과를 접근 가능한 비동기 쿼리로 대기한다. | exact-head frontend typecheck, 201 tests, build, Security/SAST/SBOM/provenance 및 독립 리뷰 | Active PR; 재검증 필요 |
| P1 | protected main에 갱신 가능한 제품·기술 gap snapshot이 없었다. | 이 문서를 PRD/TRD/ADR, exact head, PR 및 Checks에 맞춰 유지한다. | material merge 뒤 protected-head 재수집 | Active PR |

## Boundary와 non-claims

PR #971의 고유 제품 delta는 immutable `step-security/harden-runner` v2.21.0 SHA 갱신이다. 이 RCA는 frontend 동작이나 한국어 UI copy를 변경하지 않는다. 새 exact-head Checks가 완료되기 전에는 GREEN, merge-ready 또는 릴리스라고 주장하지 않는다.
