# 변경 사항

## 🎨 Palette: ERD 테이블 및 컬럼 편집 기능 구현

### ✨ 추가된 기능 (Features)
- ReactFlow 노드를 더블 클릭하여 테이블 이름 및 코멘트를 수정할 수 있는 편집 모달 기능 구현.
- 편집 모달 내에서 개별 테이블의 컬럼을 추가/삭제/수정(컬럼명, 데이터타입, PK/NN 여부)할 수 있는 기능 제공.
- 노드 삭제 시 관련 Edge 또한 삭제하는 로직 추가.
- 접근성 개선을 위해 파괴적인 액션(테이블 삭제, 컬럼 삭제) 시 사용자 확인 창(`window.confirm`) 추가.
- 새롭게 추가된 UI 플로우를 위한 기본 테스트 코드(`App.editTable.test.tsx`, `TableNode.test.tsx`) 추가 및 Vitest 프레임워크 셋업 보완.

### 🐛 개선 (Improvements)
- 대규모 ERD 검색 성능 개선: `flatMap`, 배열 복사(`...`), 그리고 긴 문자열 조인(`join(" ")`)을 제거하고 `for` 루프와 `break`/`continue`를 활용하여 조건 성립 즉시 평가를 중단(short-circuit)하도록 개선함으로써 사용자 입력 지연(Input Lag)과 불필요한 메모리 할당(Garbage Collection 압박)을 해결.
- 불필요한 백엔드 포맷팅 이슈(`ruff` 포맷) 해결.
- 테스트 커버리지를 높이기 위해 기본 단위 테스트 환경(jsdom, @testing-library) 구축 및 활용.
