
## 2024-05-24 - [검색 필터링 성능 최적화와 불변 상태 검증]
**Learning:** React Flow에서 노드 검색 시 렌더링 루프 내에서 컬럼 순회와 문자열 변환이 O(N * C)의 반복 비용 및 객체/GC 부담을 유발한다. 하지만 이 값을 `WeakMap`에 캐시할 때는 원본 객체(`node.data`)를 참조 키로 사용하므로, 상태가 변경될 때 캐시를 무효화(invalidate)하려면 동일 객체 내부를 갱신하는 것(mutation)을 반드시 차단하고 새로운 불변 객체(immutable state)로 전면 교체하도록 계약(contract)해야 한다.
**Action:** `WeakMap` 캐싱 적용과 더불어, TypeScript의 `readonly` 및 `ReadonlyArray` 수식어를 사용해 프로덕션 데이터 모델(`TableNodeData`와 하위 `columns`)의 수정을 빌드 타임에 차단하여 갱신 계약을 강화해야 한다. 성능 평가 시 타이머에만 의존하기보다는, 결정론적인 캐시 미스 카운터 추적(e.g., `_searchCacheMetrics.misses`)과 같이 통제된 단위 벤치마크/기대 범위를 테스트 캡슐화 내부에 추가한다.
