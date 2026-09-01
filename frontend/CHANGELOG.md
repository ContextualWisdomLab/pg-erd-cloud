# CHANGELOG

## [Unreleased]
### Added
- **관계 기반 ERD 자동 정렬**: 스냅샷 최초 배치와 `ERD 자동 정렬`이 동일한 관계 기반 Dagre 레이아웃을 사용합니다. 참조 대상 테이블을 종속 테이블보다 먼저 배치하고 순환·병렬 관계·독립 테이블·Unicode 식별자를 결정론적으로 처리하며, 레이아웃 계산이 실패하거나 유효하지 않은 좌표를 반환하면 기존 위치와 이전 Undo 경계를 보존합니다.
- **테이블 및 컬럼 편집 기능**: UI 패널을 통해 노드를 선택하고, 테이블의 이름/코멘트를 수정하며, 컬럼을 추가/수정/삭제하거나 테이블을 삭제할 수 있는 기능 추가.
- **테스트 추가**: 프론트엔드 테스트 커버리지 100% 목표 달성을 위해 `cardinality.ts`, `types.ts`, `export.ts` 의 미달성 분기 및 함수 테스트 추가 (`cardinality_extra.test.ts` 등).
- `.gitignore` 파일에 `coverage/` 폴더를 추가하여 불필요한 테스트 아티팩트가 커밋되지 않도록 보완.

### Security
- `postcss` 트랜지티브 의존성을 `overrides`로 `^8.5.18`(8.5.25로 해석)에 고정해 GHSA-r28c-9q8g-f849(High, source-map 자동 로딩의 경로 순회를 통한 임의 `.map` 노출)을 제거했습니다. postcss는 Vite 빌드 툴체인 전용 트랜지티브 의존성으로 배포 런타임 경로에 없으며, 조치 후 `npm audit --audit-level=high` → High 이상 취약점 0건. 변경 범위는 `frontend/package.json`의 `overrides` 맵(`postcss` 항목 추가)과 재생성된 `frontend/package-lock.json`이며, 애플리케이션 소스는 수정하지 않았습니다.
