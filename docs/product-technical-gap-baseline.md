# Product / Technical Gap Baseline

기준일: 2026-09-10

`pg-erd-cloud`의 ERD export와 handle encoding은 buyer-visible diagram/export 경로다. 성능 변경은 기능 동등성과 실제 브라우저·런타임 측정이 함께 있어야 완료로 인정한다.

## PR #1114 — export / handle allocation 후보

현재 변경은 `Array.from(string)`을 `for...of`로 바꾸고, 일부 `Array.find()` callback 및 edge별 임시 `Set` 생성을 명시적 loop/in-place aggregation으로 바꾼다. source diff만으로는 GC pause 감소나 buyer-visible latency 향상을 입증할 수 없다. 특히 PR 설명의 synthetic loop 측정은 실제 ERD node/column/edge 분포, browser runtime, export serialization 비용을 보존하지 않는다.

### 보존해야 하는 계약

- `sanitizeHandleId`는 빈 문자열, ASCII, CJK, emoji/astral Unicode scalar에서 기존 handle ID를 byte-for-byte 보존한다.
- FK source/target handle resolution은 기존 `find()` 경로와 동일한 first-match semantics를 유지한다.
- explicit `sourceColumns`/`targetColumns`, handle fallback, PK/non-PK fallback의 export 결과가 기존 protected comparator와 동일해야 한다.
- data-dictionary foreign-key 표시의 column/handle membership, duplicate 제거, ordering을 보존한다.

### 성능 acceptance

PR #1114를 성능 개선으로 Ready 처리하기 전에는 representative/right-cleared ERD workload에서 동일 browser/runtime/CPU를 사용해 protected comparator와 current head를 반복 측정한다. export DDL/data-dictionary/diagram 경로의 median과 p95, main-thread CPU, allocation/heap 및 GC를 함께 기록한다. synthetic-only loop, sample 축소, 비현실적인 warm-cache 조건만으로 buyer-visible 성능을 주장하지 않는다.

p95가 20 ms를 넘는 buyer path라면 profile에서 실제 병목이 이 loop인지 먼저 확인한다. 개선이 통계적·운영상 의미 없거나 callback/collection 변경이 hot path가 아니면 production churn을 되돌리는 것이 기본 선택이다.

### 현재 상태

구현 후보는 유지하되 성능 수치와 일반화된 GC 주장은 검증 전 가설로 취급한다. current-head application tests, Security Scan/SAST/CodeQL과 기능 동등성 regression, representative benchmark evidence, current-head independent review가 모두 갖춰지기 전에는 merge/release-ready가 아니다.
