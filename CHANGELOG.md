# 변경 사항

## 🎨 Palette: ERD 테이블 및 컬럼 편집 기능 구현

### ✨ 추가된 기능 (Features)
- ReactFlow 노드를 더블 클릭하여 테이블 이름 및 코멘트를 수정할 수 있는 편집 모달 기능 구현.
- 편집 모달 내에서 개별 테이블의 컬럼을 추가/삭제/수정(컬럼명, 데이터타입, PK/NN 여부)할 수 있는 기능 제공.
- 노드 삭제 시 관련 Edge 또한 삭제하는 로직 추가.
- 접근성 개선을 위해 파괴적인 액션(테이블 삭제, 컬럼 삭제) 시 사용자 확인 창(`window.confirm`) 추가.
- 새롭게 추가된 UI 플로우를 위한 기본 테스트 코드(`App.editTable.test.tsx`, `TableNode.test.tsx`) 추가 및 Vitest 프레임워크 셋업 보완.

### 🐛 개선 (Improvements)
- 불필요한 백엔드 포맷팅 이슈(`ruff` 포맷) 해결.
- 테스트 커버리지를 높이기 위해 기본 단위 테스트 환경(jsdom, @testing-library) 구축 및 활용.

## [0.1.1] - 2024-07-06
### 추가됨
- ERD 노드 자동 정렬 기능에 `dagre` 알고리즘을 도입하여 테이블 간의 관계(Edge)를 기반으로 직관적인 계층형 레이아웃을 제공합니다.
### 변경됨
- 기존의 단순 이름순 격자(Grid) 정렬 로직(`computeSortedGridLayout`)을 제거하고 향상된 방향성 그래프 레이아웃(`computeDagreLayout`)으로 교체했습니다.
