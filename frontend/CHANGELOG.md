# CHANGELOG

## [Unreleased]
### Added
- **테이블 및 컬럼 편집 기능**: UI 패널을 통해 노드를 선택하고, 테이블의 이름/코멘트를 수정하며, 컬럼을 추가/수정/삭제하거나 테이블을 삭제할 수 있는 기능 추가.
- **테스트 추가**: 프론트엔드 테스트 커버리지 100% 목표 달성을 위해 `cardinality.ts`, `types.ts`, `export.ts` 의 미달성 분기 및 함수 테스트 추가 (`cardinality_extra.test.ts` 등).
- `.gitignore` 파일에 `coverage/` 폴더를 추가하여 불필요한 테스트 아티팩트가 커밋되지 않도록 보완.

### Fixed
- **PostgreSQL 식별자 관계 추론**: snapshot node에 원본 `relation_name`을 보존하고 관계 자동 추론이 이미 존재하는 정확한 키를 그대로 사용하도록 수정했습니다. 유니코드, 공백, 점 및 대소문자를 포함하는 quoted-style 식별자가 ASCII sanitizer로 변형되어 edge가 사라지는 문제를 회귀 테스트로 차단합니다.

### Security
- `postcss` 트랜지티브 의존성을 `overrides`로 `^8.5.18`(8.5.25로 해석)에 고정해 GHSA-r28c-9q8g-f849(High, source-map 자동 로딩의 경로 순회를 통한 임의 `.map` 노출)을 제거했습니다. postcss는 Vite 빌드 툴체인 전용 트랜지티브 의존성으로 배포 런타임 경로에 없으며, 조치 후 `npm audit --audit-level=high` → High 이상 취약점 0건. 변경 범위는 `frontend/package.json`의 `overrides` 맵(`postcss` 항목 추가)과 재생성된 `frontend/package-lock.json`이며, 애플리케이션 소스는 수정하지 않았습니다.
