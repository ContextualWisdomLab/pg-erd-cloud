💡 What: SVG 내보내기 시 사용하는 바운딩 박스(Bounding Box) 계산 로직을 O(N) 순회 방식으로 최적화했습니다.
🎯 Why: 기존 코드는 `Math.min(...nodes.map(...))`과 같은 형태를 4번 반복하여 사용했습니다. 이는 노드가 많은 대규모 ERD 그래프에서 중간 배열 4개 생성에 따른 O(N) 메모리 낭비를 유발하고, 자바스크립트 spread 연산자(`...`) 한계에 부딪혀 `Maximum call stack size exceeded` 크래시를 유발하는 치명적인 병목 지점이었습니다.
📊 Impact: 중간 배열 생성으로 인한 GC(가비지 컬렉션) 오버헤드가 제거되며, 노드 개수가 많은 환경에서도 브라우저 크래시 없이 안정적이고 훨씬 빠르게 SVG 내보내기가 실행됩니다.
🔬 Measurement: `frontend/src/erd/export.ts`의 `exportDiagramSvg` 함수에서 `map()`과 `...` 연산자가 제거되었는지, 테스트 커버리지(`pnpm run test --coverage`)가 정상적으로 통과하는지 확인할 수 있습니다.
