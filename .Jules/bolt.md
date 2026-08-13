## 2025-06-27 - [Map Initialization Overhead]
**Learning:** Initializing Maps with `new Map(array.map(...))` creates unnecessary intermediate arrays, consuming memory and triggering garbage collection overhead, especially noticeable when dealing with many nodes.
**Action:** Use a `for...of` loop to directly `map.set()` elements rather than creating an intermediate array of tuples, especially in frequently executed or rendering paths.

## 2024-05-18 - [동시성을 이용한 데이터베이스 풀러 프로브 최적화]
**Learning:** 데이터베이스 풀러(PgBouncer, PgCat 등)의 존재 여부를 순차적으로 확인하는 과정에서 최악의 경우 연결 지연이 심하게 발생할 수 있음을 확인했습니다. (특히 설정된 timeout 만큼 첫 번째 확인 대상에서 대기하게 되는 경우).
**Action:** `backend/app/db.py` 내부의 `get_pooler_detection` 함수에서 `for` 루프를 사용한 순차적 접근 방식을 `asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)`를 활용한 동시 접근 방식으로 리팩터링했습니다. 이를 통해 응답이 가장 빠른 풀러 결과를 즉시 반환하고, 대기 중인 다른 task들을 `cancel()` 처리하여 연결 초기화 병목 현상을 방지하고 latency를 크게 낮추었습니다.
