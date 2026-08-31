# Prisma relation export contract

## Scope

PR #1015 optimizes Prisma export relation lookup without weakening schema integrity. The exporter resolves current encoded ERD handles and legacy raw handle suffixes through separate per-node indexes, indexes primary-key and relation metadata during preprocessing, and performs indexed lookups while emitting model fields.

## Integrity decision

Prisma defines the scalar field named in `@relation(fields: [...])` as the relation scalar field that represents the database foreign key. Prisma also requires relation fields to model the two sides of a relation and requires explicit relation names when multiple relations between the same models must be disambiguated (Prisma Data, Inc., 2026).

Accordingly, one ERD source scalar field is not silently expanded into multiple annotated Prisma relation fields. If more than one edge claims the same source scalar field, export fails closed with an actionable error telling the customer to remove the duplicate relation edge or use separate foreign-key columns. This avoids emitting duplicate or ambiguous Prisma fields while preserving the underlying ERD instead of guessing a schema transformation.

Current encoded handles and legacy raw handles occupy separate namespaces. If the same handle text could identify different columns (for example, encoded `a` → `c-0061` while a different legacy column is literally named `c-0061`), export fails closed and tells the customer to rename the colliding column or reconnect the relation. Node IDs and column handles are also stored as separate map dimensions rather than colon-concatenated composite strings.

## Performance and compatibility contract

- Build node, handle-to-column, primary-key, incoming-relation, and outgoing-relation indexes once.
- Remove the previous explicit per-edge `columns.find()` scan, changing the exporter from O(N×C + E×C) to expected O(N×C + E) under the conventional hash-backed `Map` implementation used by supported JavaScript runtimes.
- Treat constant-time `Map` access as an implementation-level expected-performance assumption, not an ECMAScript language guarantee. ECMAScript requires `Map` implementations to provide average access time sublinear in collection size, while allowing hash tables or other mechanisms (Ecma International, 2026).
- Accept both the current encoded `sourceColumnHandleId` / `targetColumnHandleId` representation and legacy raw handle suffixes.
- Preserve the exact source and referenced database column names when rendering Prisma fields.
- Regression coverage lives in `frontend/src/erd/__tests__/prisma_relation_index.test.ts` and covers duplicate-relation fail-closed behavior, encoded/raw namespace collisions on both source and target handles in both column orders, node/column delimiter collisions, legacy raw handle compatibility, and a guard that relation indexing does not call `Array.find` on the source column array.

Fredman, Komlós, and Szemerédi (1984) provide the primary algorithmic literature establishing that hash-based dictionary structures can support constant-time lookup under stronger construction assumptions. That paper is cited as the data-structure rationale for replacing repeated linear scans with indexed lookup; it is not used to claim that ECMAScript `Map` itself inherits FKS worst-case guarantees.

## Traceability

- Pull request: #1015
- Production implementation: `frontend/src/erd/prisma.ts`
- Regression tests: `frontend/src/erd/__tests__/prisma_relation_index.test.ts`
- Review findings addressed: duplicate relation integrity coverage; per-relation O(C) column scans; encoded/raw handle namespace collisions; delimiter-safe node/column indexing; legacy raw-handle compatibility coverage.
- Standards evidence: ECMAScript 2026 `Map` performance contract; Prisma relation semantics.
- Research evidence: Fredman et al. (1984) on constant-time dictionary lookup under perfect-hashing assumptions.

## References

Ecma International. (2026). *ECMAScript® 2026 language specification: Map objects* (Section 24.1). https://tc39.es/ecma262/2026/multipage/keyed-collections.html

Fredman, M. L., Komlós, J., & Szemerédi, E. (1984). Storing a sparse table with O(1) worst case access time. *Journal of the ACM, 31*(3), 538–544. https://doi.org/10.1145/828.1884

Prisma Data, Inc. (2026). *Relations*. Prisma Documentation. Retrieved August 31, 2026, from https://www.prisma.io/docs/orm/prisma-schema/data-model/relations
