## 2024-06-21 - [Avoid Map Creation on High-Frequency React Arrays]
**Learning:** React Flow updates the `nodes` array extremely frequently (e.g., during dragging). Creating a `Map` (like `nodesById`) using a `useMemo` that depends on this array forces a full O(N) iteration, memory allocation, and GC on every single micro-update.
**Action:** For standard node lookups in a typically sized ERD (10-500 tables), prefer an O(N) `Array.prototype.find()` without allocating intermediate memory structures over building and looking up a `Map`.
## 2026-06-19 - Endless Polling in React Components
**Learning:** React `useEffect` with `setInterval` for polling can easily become a performance bottleneck (unnecessary network calls, state updates, and potential memory leaks) if the termination condition isn't handled correctly when the polled job reaches a terminal state.
**Action:** Always ensure polling mechanisms have a clean exit strategy by clearing intervals once a terminal state (like `succeeded`, `failed`, or `not_found`) is reached.

## 2026-06-19 - Expensive useMemo Keys
**Learning:** Using `JSON.stringify` on large data objects as a dependency for `useMemo` is an expensive hack to prevent re-renders, causing severe performance issues as the data size grows.
**Action:** Rely on proper reference management and stop unnecessary state updates (like fixing endless polling) instead of using deep stringification hacks for `useMemo` dependencies.
## 2026-06-20 - O(N^2) loops for finding items in export
**Learning:** Nested array `.find()` iterations within loops parsing graph connections result in O(N^2) complexity, significantly degrading UI performance for large outputs.
**Action:** Always pre-compute a lookup `Map` in O(N) when multiple specific node lookups are needed within iterative processes.
## 2024-05-24 - Optimize O(N*M) lookups to O(1) Sets in React state mapping
- **Learning**: Using `array.some(...)` inside `array.map(...)` can become a significant performance bottleneck (O(N*M)) when dealing with large sets of recommendations or nodes.
- **Action**: Always pre-compute a `Set` or dictionary outside the mapping loop for fast O(1) signature-based lookups.
- **Safety**: When moving logic into a state updater callback like `setNodes((currentNodes) => ...)`, make sure to evaluate any validation checks (like checking if an index is already applied) **inside** the callback to prevent stale closures. Avoid unchecked properties like `columns.join` if `columns` could be undefined.
## 2024-06-21 - Optimize O(N^2) Map building
**Learning:** Building Maps inside loops using `map.set(key, [...(map.get(key) || []), item])` leads to O(N^2) complexity and enormous intermediate garbage generation for large datasets.
**Action:** Use an O(1) amortized append instead: pull the list with `.get(key)` and use `.push(item)`. Create the array only when inserting the first item.

## 2026-06-25 - Avoid Redundant map.set() on Mutable Map Values
**Learning:** When updating mutable values stored in a `Map`, such as `Set` or `Array`, calling `map.set(key, value)` after every mutation repeats work once the entry already exists.
**Action:** Create and store the mutable value only when `map.get(key)` misses. After that, mutate the retrieved collection directly with `.add()` or `.push()`.
## Performance Issue: Inefficient Route Metric Priming
The previous implementation of `prime_http_metrics` resulted in an O(M * R) Cartesian product loop creating metric series for every HTTP method across every single route.

## Fix
Optimized metric route processing to O(N) by creating a mapping of routes directly to their active methods and iterating solely over those active methods.

## Benchmark Results
100 unique routes, 1 unique method each (100 total combinations):
- Before: ~820.62ms
- After: ~1.17ms
## 2026-06-25 - Avoid unbounded Math.min/Math.max spreads
**Learning:** Spreading dynamically sized arrays into variadic functions like `Math.max(...values)` creates intermediate arrays and can exceed JS engine argument-count limits, often surfacing as `RangeError` variants such as "Too many arguments".
**Action:** For unbounded frontend collections such as ERD nodes, calculate min/max bounds with an iterative loop instead of `Math.min(...array)` or `Math.max(...array)`.

## 2024-07-01 - Avoid O(N^2) Complexity in Graph Exporters
**Learning:** Nested array `.find()` or `.some()` iterations within loops parsing graph connections result in O(N^2) complexity, significantly degrading UI performance for large outputs (like exporting Mermaid diagrams where we check every column of every node against every edge).
**Action:** Always pre-compute a lookup `Map` or `Set` in O(N) or O(E) when multiple specific node or edge lookups are needed within iterative processes.
## 2024-05-19 - React Flow 렌더링 최적화와 JavaScript Map 자료구조 최적화
**Learning:**
1. React Flow는 노드의 위치(드래그)나 선택 상태만 변경될 때 새로운 Node 객체를 만들지만, 내부의 `data` 참조는 유지합니다. React의 `memo` 커스텀 비교 함수 상단에 `prev.data === next.data` 참조 비교(fast-path)를 추가하면, 복잡한 컬럼 리스트 비교 등 깊은 비교 연산을 건너뛸 수 있어 그래프 조작 시 렌더링 성능이 크게 향상됩니다.
2. 대규모 컬럼 및 참조 제약조건 정보를 변환할 때(O(N)), 루프 내부에서 `map.get()`으로 불러온 배열이나 Set에 단순히 `push()`나 `add()` 하는 대신 다시 `map.set()`을 호출하는 중복 연산은 GC 압박을 가중시킵니다. 참조 자료구조에서는 초기 생성 시에만 `set`을 호출하고 그 이후엔 객체를 직접 수정하는 것이 성능 최적화에 유리합니다.

**Action:**
1. React Flow를 활용하는 경우, 노드의 속성이 분리된 형태(위치 vs 데이터)를 인식하고 `memo` 비교 시 참조 비교(fast-path)를 적극 적용하여 비용이 큰 깊은 비교를 회피하도록 합니다.
2. 루프 내에서 가변 컬렉션(배열/Set 등)을 Map에 저장하여 다룰 때는 `if (!collection) { collection = []; map.set(key, collection); } collection.push(val);` 패턴을 엄격하게 사용하여 성능 저하 및 불필요한 메모리 재할당을 피합니다.
## 2024-06-25 - Avoid O(N) Map.set inside Loops for Existing Arrays/Sets
**Learning:** When building Maps containing arrays or Sets in a loop, continually calling `map.set(key, list)` even after `list` is retrieved from `map.get()` causes unnecessary hashing and re-balancing overhead.
**Action:** Only call `map.set()` when the array or Set doesn't exist yet (during creation). If the collection already exists in the Map, mutate it directly (e.g. `list.push` or `set.add`) without re-setting it in the Map.
