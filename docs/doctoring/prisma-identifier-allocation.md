# Prisma identifier allocation

## Decision

Canvas Prisma export and snapshot ORM export allocate model, field, and
relation names from a pinned Prisma 6 contract instead of a one-pass character
replacement. The grammar is `[A-Za-z][A-Za-z0-9_]*`. Reserved names come from
the Prisma Schema API keywords, scalar type names, and the prisma-engines
reserved-model-name table. Allocation sorts by source text so input order
cannot change the mapping. When a generated name differs from the database or
canvas source, the exporter writes `@map` / `@@map`. If a unique name cannot
be allocated inside 10,000 attempts, export fails closed with a fixed comment
and a downloadable diagnostic manifest that authorized users can inspect.

## Why

Buyers paste generated Prisma into `prisma validate` and `prisma generate`.
A sanitizer that only replaces punctuation can emit reserved names (`model`),
collapse `order-item` / `order item` / `order_item`, or map reserved `model`
onto an existing `M_model` table. Those failures appear as a broken schema,
not as an ERD drawing issue. Preserving the original PostgreSQL identifier
through `@map` keeps reverse-engineered names recoverable after the generated
token is made legal.

## Invariants

- Generated identifiers always match the Prisma grammar.
- Reserved schema keywords are rejected case-insensitively (`model`, `Model`,
  `MODEL`).
- `model` and `M_model` never share a generated name.
- The same source set always receives the same generated names.
- Public failure copy does not echo table, column, or user-controlled text.
- Authorized users can download the source→generated manifest after a failure.

## Verification

Frontend: `frontend/src/erd/__tests__/prismaIdentifiers.test.ts` and
`frontend/src/erd/__tests__/prisma.test.ts` cover reserved names, punctuation
collisions, Unicode/NFC/NFD, hex-encoded FK handles from reverse engineering,
and fail-closed export. Backend: `backend/tests/test_prisma_identifiers.py`
and `backend/tests/test_orm_codegen.py` cover the same contract on snapshot
JSON, including a non-reflecting failure path.

## Operational monitoring and rollback

Monitor Prisma export failures, manifest downloads, and `prisma validate`
rejections reported by customers. Roll back by restoring the previous
character-replacement sanitizer only if a verified regression requires it;
doing so reopens reserved-name and collision defects.

## References

Chen, P. P.-S. (1976). The entity-relationship model—toward a unified view of
data. *ACM Transactions on Database Systems, 1*(1), 9–36.
https://doi.org/10.1145/320434.320440

Prisma Data, Inc. (2026). *Prisma schema reference: Naming conventions*.
https://www.prisma.io/docs/orm/reference/prisma-schema-reference

The Unicode Consortium. (2024). *The Unicode Standard, Version 16.0.0*.
https://www.unicode.org/versions/Unicode16.0.0/

prisma-engines contributors. (2026). *reserved_model_names.rs* (Git commit on
`main`, retrieved August 16, 2026).
https://github.com/prisma/prisma-engines/blob/main/psl/parser-database/src/names/reserved_model_names.rs
