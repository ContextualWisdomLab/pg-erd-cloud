# ADR 0011 — Collision-free Prisma identifier allocation

## Status

Accepted

## Context

Issue #898 records a buyer-visible Prisma export gap: character replacement
can emit reserved names, collapse distinct PostgreSQL identifiers, and omit
`@map` / `@@map`. PR #894 removed an incomplete workaround and left the
allocator as a dedicated follow-up.

## Decision

Ship one allocator used by canvas export (`frontend/src/erd/prisma.ts`) and
snapshot ORM export (`backend/app/spec/orm_codegen.py`). Pin reserved names
to Prisma Schema API keywords plus the prisma-engines client reserved list.
Fail closed with a fixed message and a diagnostic manifest.

## Consequences

- Generated Prisma is legal under the pinned grammar even when source names
  are quoted, multilingual, or reserved.
- Frontend and backend preferred-name styles stay different (`users` vs
  `Users` / `Member`); only collision and reserved-name policy is shared.
- Prisma CLI `6.19.3` is pinned in the frontend lockfile. CI runs both
  `prisma format` and `prisma validate` against a multi-schema composite-key
  fixture before accepting the generated schema path.

## References

See `docs/doctoring/prisma-identifier-allocation.md`.
