# Searchable-text cache authority

## Decision

ERD search may cache the lower-cased searchable text derived from `TableNodeData` in a `WeakMap<TableNodeData, string>`. The cache key is the immutable table-data object, not the React Flow `Node` wrapper. Position-only wrapper replacement may therefore reuse the cached text when it retains the same `node.data` reference. Any searchable-field change must replace the `TableNodeData` object and the changed nested column object before the new value is searched.

The cached text contains only the fields already searched by the product: table title, table comment, column name, data type, and column comment. It carries no position, selection, credential, network, or highlight authority. A future integration that allows in-place mutation must add a reviewed revision or content-fingerprint invalidation contract before such mutation is accepted.

## Verification

Focused tests require all searchable fields to invalidate through immutable replacement and directly prove that a new React Flow node wrapper retaining the same `TableNodeData` object produces no additional cache miss. A fixed workload of 500 nodes with 100 columns each proves the second search over the same data identities adds zero cache misses. These are deterministic identity/allocation contracts, not wall-clock performance claims.

## Operations and rollback

Monitor browser memory growth, search-result correctness after schema refreshes, and cache-miss behavior in realistic large diagrams. If an upstream editor begins mutating `TableNodeData` in place, fail the immutable-data contract and either restore uncached search or introduce an explicit revision/content fingerprint before retaining memoization.

## References

Ecma International. (2026). *ECMAScript® 2026 language specification* (17th ed.). https://262.ecma-international.org/

Michie, D. (1968). “Memo” functions and machine learning. *Nature, 218*, 19–22. https://doi.org/10.1038/218019a0

Mozilla Contributors. (2026). *WeakMap*. MDN Web Docs. https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/WeakMap
