# 변경 사항

## 🎨 Palette: ERD 노드 자동 정렬 기능(Dagre) 도입

### ✨ 추가된 기능 (Features)
- `dagre` 알고리즘을 도입하여 노드와 엣지(FK) 관계를 고려한 계층적(DAG) 자동 배치(`computeDagreLayout`) 기능 구현
- ERD 툴바의 '자동 정렬' 버튼 클릭 시 기존 단순 그리드 배치의 선 꼬임 현상을 획기적으로 개선
- 관련 로직의 100% 테스트 커버리지 달성을 위한 단위 테스트(`layout.test.ts`) 작성

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
