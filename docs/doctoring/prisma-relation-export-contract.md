# Prisma relation export contract

## Scope

PR #1015 optimizes Prisma export relation lookup without weakening schema integrity. The exporter now resolves current encoded ERD handles to their real column names once, indexes primary-key and relation metadata in linear preprocessing, and performs O(1) lookups while emitting model fields.

## Integrity decision

Prisma defines the scalar field named in `@relation(fields: [...])` as the relation scalar field that represents the database foreign key. Prisma also requires relation fields to model the two sides of a relation and requires explicit relation names when multiple relations between the same models must be disambiguated (Prisma Data, Inc., 2026).

Accordingly, one ERD source scalar field is not silently expanded into multiple annotated Prisma relation fields. If more than one edge claims the same source scalar field, export fails closed with an actionable error telling the customer to remove the duplicate relation edge or use separate foreign-key columns. This avoids emitting duplicate or ambiguous Prisma fields while preserving the underlying ERD instead of guessing a schema transformation.

## Performance and compatibility contract

- Build node, handle-to-column, primary-key, incoming-relation, and outgoing-relation indexes once.
- Avoid per-edge `columns.find()` scans; relation indexing remains O(N×C + E) for N nodes, C columns per node, and E edges.
- Accept both the current encoded `sourceColumnHandleId` / `targetColumnHandleId` representation and legacy raw handle suffixes.
- Preserve the exact source and referenced database column names when rendering Prisma fields.
- Regression coverage lives in `frontend/src/erd/__tests__/prisma_relation_index.test.ts` and includes duplicate-relation fail-closed behavior plus a guard that relation indexing does not call `Array.find` on the source column array.

## Traceability

- Pull request: #1015
- Production implementation: `frontend/src/erd/prisma.ts`
- Regression tests: `frontend/src/erd/__tests__/prisma_relation_index.test.ts`
- Review findings addressed: duplicate relation integrity coverage; per-relation O(C) column scans.

## Reference

Prisma Data, Inc. (2026). *Relations*. Prisma Documentation. Retrieved August 31, 2026, from https://www.prisma.io/docs/orm/prisma-schema/data-model/relations
