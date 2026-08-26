# PostgreSQL identifier fidelity in relationship inference

## Status

Implemented in `frontend/src/erd/autoInfer.ts` and guarded by `frontend/src/erd/__tests__/autoInfer.postgresIdentifiers.test.ts`.

## Defect

Relationship inference used a display title as an identity source, split it on every period, and then passed the discovered name through an ASCII-only replacement function. Those transformations are not SQL quoting boundaries. They can silently change PostgreSQL relation identity for quoted identifiers containing spaces, non-Latin letters, mixed case, or periods, and can alias `Order.Items` to an unrelated `Items` table.

## Decision

Snapshot conversion carries PostgreSQL's exact `relation_name` as structured node data. Relationship inference uses that value as its identity key. A title-only fallback exists only for manually constructed legacy nodes and removes at most the first schema separator; it does not collapse subsequent periods or create trailing-segment aliases.

```text
snapshot relation_name
→ exact relation identity key
→ `_id` naming candidate
→ exact map lookup
→ inferred edge
```

The browser helper does not construct or execute SQL. Identifier rendering and SQL generation remain responsible for context-aware quoting at their own boundaries. Character deletion or last-segment aliasing is not SQL-injection prevention and can change which object is referenced.

## Invariants

- Snapshot relation names are propagated as structured data rather than re-parsed from presentation text.
- Unicode, mixed-case, space-containing, and period-containing quoted relation names retain exact identity.
- `Order.Items` is not registered as an alias for `Items`; ambiguity resolves only by exact relation name.
- The inference heuristic still requires a matching existing table key; arbitrary column text cannot create a new target object.
- Self-relations remain excluded by exact relation-name comparison.
- SQL execution authority is unchanged and remains outside the browser inference helper.

## Test-first evidence

The regression suite was added before the production repair and covers Korean, space-containing mixed-case, period-containing quoted identifiers, and the ambiguous pair `Order.Items` versus `Items`. On the protected-base implementation the test does not compile because structured `relation_name` is absent; after that representation is introduced, the ambiguity assertion also prevents reintroducing trailing-segment aliasing.

Exact-head repository CI, type checking, frontend coverage, security workflows, and independent review remain authoritative; commit order records TDD intent but does not replace those gates.

## Monitoring and rollback

Monitor inferred candidates and accepted inferred edges by coarse identifier class without logging full customer identifiers. A post-release drop limited to non-ASCII or quoted identifiers indicates a regression. Do not roll back to ASCII rewriting or terminal-segment aliasing. Roll back only to an implementation that preserves exact model identity and applies quoting exclusively when SQL is rendered.

## References

PostgreSQL Global Development Group. (2026). *4.1. Lexical structure*. In *PostgreSQL 18 documentation*. https://www.postgresql.org/docs/18/sql-syntax-lexical.html

PostgreSQL Global Development Group. (2026). *9.4. String functions and operators*. In *PostgreSQL 18 documentation*. https://www.postgresql.org/docs/18/functions-string.html

Rahm, E., & Bernstein, P. A. (2001). A survey of approaches to automatic schema matching. *The VLDB Journal, 10*(4), 334–350. https://doi.org/10.1007/s007780100057

Rahm and Bernstein distinguish name/language evidence from structural and constraint evidence in schema matching. That distinction supports keeping the identifier token intact at the name-matching boundary instead of destructively normalizing it into a different database object identity.
