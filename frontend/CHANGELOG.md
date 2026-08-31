# CHANGELOG

## [Unreleased]
### Performance
- **Prisma 관계 내보내기 선형 인덱싱 및 무결성 강화**: 기존 관계 탐색의 O(N*C + E*C) 경로를 노드별 컬럼·관계 인덱스로 전처리해 O(N*C + E)로 줄였습니다. current encoded handle과 legacy raw handle은 서로 분리된 namespace에서 해석하며, 두 형식이 서로 다른 컬럼을 가리키는 모호한 handle은 잘못된 schema를 생성하지 않고 컬럼 이름 변경 또는 관계 재연결을 안내하며 fail-closed 합니다. 하나의 scalar field에 여러 관계 edge가 연결된 경우에도 중복 edge 제거 또는 별도 foreign-key column 사용을 안내하며 내보내기를 중단합니다.
### Added
- **테이블 및 컬럼 편집 기능**: UI 패널을 통해 노드를 선택하고, 테이블의 이름/코멘트를 수정하며, 컬럼을 추가/수정/삭제하거나 테이블을 삭제할 수 있는 기능 추가.
- **테스트 추가**: 프론트엔드 테스트 커버리지 100% 목표 달성을 위해 `cardinality.ts`, `types.ts`, `export.ts` 의 미달성 분기 및 함수 테스트 추가 (`cardinality_extra.test.ts` 등).
- `.gitignore` 파일에 `coverage/` 폴더를 추가하여 불필요한 테스트 아티팩트가 커밋되지 않도록 보완.

### Security
- `postcss` 트랜지티브 의존성을 `overrides`로 `^8.5.18`(8.5.25로 해석)에 고정해 GHSA-r28c-9q8g-f849(High, source-map 자동 로딩의 경로 순회를 통한 임의 `.map` 노출)을 제거했습니다. postcss는 Vite 빌드 툴체인 전용 트랜지티브 의존성으로 배포 런타임 경로에 없으며, 조치 후 `npm audit --audit-level=high` → High 이상 취약점 0건. 변경 범위는 `frontend/package.json`의 `overrides` 맵(`postcss` 항목 추가)과 재생성된 `frontend/package-lock.json`이며, 애플리케이션 소스는 수정하지 않았습니다.
