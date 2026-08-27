# PostgreSQL identifier fidelity in relationship inference

## Status

Implemented in `frontend/src/erd/convert.ts` and `frontend/src/erd/autoInfer.ts`, with product-boundary regression coverage in `frontend/src/erd/__tests__/autoInfer.postgresIdentifiers.test.ts`.

## Defect

Relationship inference first discovered an existing target table name and then passed that already-known model identity through an ASCII-only replacement function before the map lookup. That second transformation was not an SQL quoting boundary. It could silently remove spaces, non-Latin letters, punctuation, and other characters that PostgreSQL permits in quoted identifiers, causing valid customer schemas such as `public.사용자`, `public."Order Items"`, and a quoted relation whose name contains a dot to lose inferred edges.

The stale branch also reconstructed a relation name by splitting the display title on `.`. That representation is ambiguous when the quoted relation name itself contains a dot.

## Decision

Snapshot-backed graph nodes preserve the exact PostgreSQL `relation_name` separately as `TableNodeData.relationName`. Relationship inference indexes nodes by that exact model identity and probes the existing map without sanitizing or rewriting the selected key. A title-splitting fallback remains only for manually created or legacy nodes that predate the explicit relation-name field.

```text
snapshot relation_name
→ exact node relationName
→ `_id` naming candidate
→ exact map lookup
→ inferred edge
```

Self-reference exclusion uses node identity rather than a parsed name fragment. The inference helper does not construct or execute SQL; identifier quoting remains the responsibility of SQL-rendering boundaries.

## Invariants

- Snapshot-backed relation names are never reconstructed from display text.
- Existing table keys are never passed through a character-deleting sanitizer during relationship lookup.
- Unicode, whitespace, mixed case, and dots retain exact identity when they are part of a PostgreSQL relation name.
- The heuristic can only target a node already present in the graph map; arbitrary column text cannot create a new database object or execution authority.
- Self-relations are excluded by node identity.
- SQL rendering and execution authority are unchanged.

## Test-first evidence

Commit `4cd28702107f07e5eb4ff1761f8c8996975e2469` introduced the product-boundary regression before the production repair. The test constructs snapshot-backed relations using Korean, space-containing, and dot-containing names and requires the expected inferred edges. Subsequent commits preserve the exact relation identity on graph nodes and remove the lossy sanitizer from inference.

Exact-head hosted tests, type checking, coverage, security workflows, and independent review remain authoritative. Commit order records the test-first development sequence but does not replace those gates.

## Monitoring and rollback

Monitor inferred-candidate and accepted-edge counts by coarse identifier class without logging complete customer identifiers. A release-specific drop isolated to non-ASCII or quoted identifiers is a regression signal. Rollback must not restore ASCII rewriting or display-title parsing as the canonical model identity; revert only to an implementation that preserves exact relation identity and applies quoting at SQL-rendering boundaries.

## References

PostgreSQL Global Development Group. (2026). *4.1. Lexical structure*. In *PostgreSQL 18 documentation*. https://www.postgresql.org/docs/18/sql-syntax-lexical.html
