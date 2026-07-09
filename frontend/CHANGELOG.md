# CHANGELOG

## [Unreleased]
### Added
- **테이블 및 컬럼 편집 기능**: UI 패널을 통해 노드를 선택하고, 테이블의 이름/코멘트를 수정하며, 컬럼을 추가/수정/삭제하거나 테이블을 삭제할 수 있는 기능 추가.
- **테스트 추가**: 프론트엔드 테스트 커버리지 100% 목표 달성을 위해 `cardinality.ts`, `types.ts`, `export.ts` 의 미달성 분기 및 함수 테스트 추가 (`cardinality_extra.test.ts` 등).
- `.gitignore` 파일에 `coverage/` 폴더를 추가하여 불필요한 테스트 아티팩트가 커밋되지 않도록 보완.

## 2025-02-24
- `CardinalityModal.tsx`의 동적 컬럼 입력 폼에 스크린 리더에서 각 행을 명확히 구별할 수 있도록 동적 `aria-label` 속성을 추가하여 접근성을 개선.
