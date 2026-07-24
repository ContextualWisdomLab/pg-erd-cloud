## 2026-07-13 - Precompute Lookup Structures in Export and Graph-Parsing Paths
**Learning:** Nested `.find()`/`.some()` scans inside loops over graph nodes, columns, and edges make export paths O(N^2) or worse — e.g. O(N*C*E) in the ERD export dictionary checking `edges.some()` per column, and the Mermaid exporter checking every column of every node against every edge.
**Action:** In batch/export paths, precompute lookup `Map`s or `Set`s in O(N) or O(E) first (e.g. per-node Sets of foreign-key column handles), then run the main loop with O(1) membership checks. See the 2026-06-21 hot-path entry for the case where precomputing is the wrong trade-off.

## 2026-07-12 - Hoist Search-String Parsing out of Per-Node Loops
**Learning:** During text search across many ERD nodes, re-parsing the query (splitting, trimming, `new Set()`) inside the per-node loop repeats identical work O(N) times per keystroke and adds garbage-collection pressure.
**Action:** Hoist immutable parsing and initialization out of node-evaluation loops and pass the parsed result into evaluator functions, so per-keystroke setup cost is O(1).

## 2026-07-09 - Map-Based Node Resolution in autoInfer.ts, Plus Identifier Hardening
**Learning:** Foreign-key matching ran `nodes.find` with string splitting inside an O(N) loop (O(N^2) total), plus two nested O(C) passes over the same column array. Replacing the outer scan with an O(1) `Map` lookup and merging the column passes into a single `for...of` with early exits removed the bottleneck. Table-name handling was also hardened with an allowlist sanitizer to reduce traversal/injection risk when constructing derived identifiers.
**Action:** For repeated lookups against static node trees, build an O(1) lookup `Map` up front and collapse repeated small-array passes into single-pass loops. When security scanners flag string-built identifiers, prefer genuine hardening (validation, canonicalization, safer construction); use narrowly scoped suppressions only with documented false-positive evidence.

## 2026-07-07 - Avoid new Map(array.map(...)) for Large Datasets
**Learning:** `new Map(array.map(item => [key, val]))` allocates a throwaway O(N) array of tuple arrays that the garbage collector must immediately reclaim, causing memory spikes and GC pauses during large ERD exports.
**Action:** Build the map imperatively — `const map = new Map();` then `for (const item of array) { map.set(key, item); }` — to eliminate intermediate allocations.

## 2026-06-30 - Create Keyed Collections Once, Then Mutate in Place
**Learning:** When aggregating into a `Map` of arrays or Sets, two patterns waste work: rebuilding the value on every hit (`map.set(key, [...(map.get(key) || []), item])`, which is O(N^2) with heavy intermediate garbage) and redundantly re-calling `map.set(key, list)` after the list was already retrieved (unnecessary hashing and re-balancing). The frontend `snapshotToGraph` loops over thousands of columns, so this overhead is material.
**Action:** Call `map.set()` only on first insertion — `let list = map.get(key); if (!list) { list = []; map.set(key, list); } list.push(item);` — and mutate the retrieved collection directly with `.push()`/`.add()` afterward.

## 2026-06-30 - React Flow memo Comparators Need a data Reference Fast-Path
**Learning:** React Flow creates new Node objects when only position or selection changes but keeps the same `data` reference. A custom `memo` comparator that starts with a `prev.data === next.data` reference check skips deep column-list comparison during drags, which materially improves rendering while manipulating the graph.
**Action:** In React Flow node components, exploit the position-vs-data split: put a reference-equality fast-path at the top of `memo` comparators before any deep comparison.

## 2026-06-30 - Avoid Unbounded Math.min/Math.max Spreads
**Learning:** `Math.min(...array)` / `Math.max(...array)` (often preceded by an extra `.map()` pass) spread the whole array into function arguments; on large ERD collections this allocates intermediate arrays and can exceed engine argument limits, surfacing as "Maximum call stack size exceeded" or "Too many arguments" RangeErrors.
**Action:** Compute bounds for unbounded collections with a single O(N) `for` loop or `reduce` pass instead of spreading into variadic `Math` calls.

## 2026-06-29 - Fill Freshly Built Snapshot Dicts in Place (Backend)
**Learning:** Backend snapshot column dictionaries are freshly instantiated for the payload, so `add_column_examples` can safely fill missing fields in place instead of copying, and expensive example inference only needs to run when the field is actually missing.
**Action:** When post-processing freshly constructed payload dicts, mutate them in place and gate expensive inference helpers behind a missing-field check.

## 2026-06-29 - Route Metric Priming: Iterate Only Active Pairs
**Learning:** `prime_http_metrics` primed metric series for every HTTP method against every route (an O(M*R) Cartesian product); a 100-route / 1-method sample measured about 820.62ms.
**Action:** Build a route-to-active-methods mapping first and iterate only real pairs so priming scales with actual route-method combinations; the same sample dropped to about 1.17ms.

## 2026-06-29 - Keep O(N) Cache Pruning off the Auth Hot Path
**Learning:** `is_token_jti_revoked` walked the entire revoked-token cache (`_prune_revoked_token_jtis`) on every authenticated request, adding O(N) latency that grows with the number of active revocations.
**Action:** On read paths, evaluate lazily against the single requested key only; keep full-cache pruning on the write path (`revoke_token_jti`), where it still bounds memory without taxing reads.

## 2026-06-21 - Prefer find() over Fresh Maps on High-Frequency React Arrays
**Learning:** React Flow updates the `nodes` array extremely frequently (e.g. during dragging). Building a `Map` (like `nodesById`) in a `useMemo` keyed on that array forces a full O(N) iteration, allocation, and GC on every micro-update.
**Action:** For hot-path lookups on a typically sized ERD (10-500 tables), a direct `Array.prototype.find()` is cheaper than rebuilding a `Map` per update; reserve precomputed lookup maps for batch/export paths (see the 2026-07-13 entry).

## 2026-06-21 - Replace O(N*M) some()-inside-map() with Precomputed Sets
**Learning:** `array.some(...)` inside `array.map(...)` is O(N*M) and became a real bottleneck for large recommendation and node sets.
**Action:** Precompute a `Set` or keyed dictionary before the mapping loop for O(1) membership checks. When moving logic into a state-updater callback (`setNodes((current) => ...)`), re-evaluate validation checks inside the callback to avoid stale closures, and guard optional properties (e.g. `columns` may be undefined before calling `columns.join`).

## 2026-06-19 - Endless Polling in React Components
**Learning:** `useEffect` with `setInterval` polling leaks network calls, state updates, and memory when the termination condition is not tied to the polled job reaching a terminal state.
**Action:** Clear intervals as soon as a terminal state (`succeeded`, `failed`, or `not_found`) is reached so polling always has a clean exit strategy.

## 2026-06-19 - Expensive useMemo Keys
**Learning:** Using `JSON.stringify` on large data objects as a `useMemo` dependency is an expensive re-render workaround whose cost grows with the data.
**Action:** Fix the underlying reference churn (e.g. stop unnecessary state updates such as endless polling) instead of deep-stringifying dependencies.
