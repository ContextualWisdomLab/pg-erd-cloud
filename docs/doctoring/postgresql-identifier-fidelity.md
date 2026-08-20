# PostgreSQL identifier fidelity in relationship inference

## Status

Implemented in `frontend/src/erd/autoInfer.ts` and guarded by `frontend/src/erd/__tests__/autoInfer.postgresIdentifiers.test.ts`.

## Defect

The relationship-inference path first found a target table by its exact name and then passed that already-trusted map key through an ASCII-only replacement function before looking it up again. This second transformation was not an SQL quoting boundary. It silently removed spaces, non-Latin letters, punctuation, and other characters that PostgreSQL permits in quoted identifiers, so valid schemas such as `public.사용자` and `public."Order Items"` could not receive inferred relationships.

The original PR proposed tests that would freeze this lossy transformation as expected behavior. Those tests were replaced with a RED regression at the actual product boundary before changing production code.

## Decision

Relationship inference now performs an exact lookup with the key that was already discovered in `nodesByTableName`.

```text
existing table title
→ exact terminal table-name key
→ `_id` naming candidate
→ exact map lookup
→ inferred edge
```

It does not construct or execute SQL. Identifier rendering and SQL generation remain responsible for context-aware PostgreSQL quoting at their own boundaries. Removing characters from a model identifier is not a substitute for quoting and can change the object being referenced.

## Invariants

- Existing table names are never rewritten during relationship lookup.
- Unicode, mixed-case, and space-containing names retain exact identity.
- The inference heuristic still requires a matching existing table key; arbitrary column text cannot create a new target object.
- Self-relations remain excluded by the existing exact-name comparison.
- SQL execution authority is unchanged and remains outside the browser inference helper.

## Test-first evidence

Commit `6e62b0db97215a0ec50df510d0c28074dec53b02` introduced the product-boundary regression before the remedy. Under the predecessor implementation, both a Korean identifier and a space-containing mixed-case identifier failed because the second lookup used a different, rewritten string. Commit `d9b360f4a74086934143e1eef9e5f72d4ce9a93d` removed that lossy step and retained the existing O(1) map lookup.

Exact-head repository CI, type checking, frontend coverage, security workflows, and independent review remain authoritative; commit order records TDD intent but does not replace those gates.

## Monitoring and rollback

Monitor the count of inferred candidates and accepted inferred edges by identifier class without logging full customer identifiers. A post-release drop limited to non-ASCII or quoted identifiers indicates a regression. Do not roll back to ASCII rewriting. Roll back only to an implementation that preserves exact model identity and applies quoting exclusively when SQL is rendered.

## References

PostgreSQL Global Development Group. (2026). *4.1. Lexical structure*. In *PostgreSQL 18 documentation*. https://www.postgresql.org/docs/18/sql-syntax-lexical.html

PostgreSQL Global Development Group. (2026). *9.4. String functions and operators*. In *PostgreSQL 18 documentation*. https://www.postgresql.org/docs/18/functions-string.html
