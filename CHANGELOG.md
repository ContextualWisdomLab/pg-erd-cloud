# 변경 사항

## [Unreleased]
### 변경 (Changed)
- `frontend/src/App.tsx`: 노드 드래그 시 60fps로 발생하는 불필요한 전체 컴포넌트 재렌더링 방지를 위해 `WeakMap`을 도입하여 `node.data`의 파생 상태(검색 하이라이팅 등)를 캐싱하도록 개선 (⚡ Bolt)
