# DBML index import fidelity

## Decision

The DBML importer preserves the supported simple index subset as PostgreSQL-oriented snapshot evidence. Single- and multi-column indexes retain `unique`, primary-key intent, supported access methods, and explicit names. A DBML `[pk]` index becomes a primary-key constraint and does not emit a duplicate standalone index because PostgreSQL creates the enforcing index for a primary key.

A non-colliding explicit index name is preserved exactly when it is representable by PostgreSQL's default identifier storage boundary (63 UTF-8 bytes) and does not contain a NUL character. The generated DDL quotes that identifier rather than deleting spaces, non-Latin characters, or case distinctions. If a source index name would collide with an existing relation/index name in the same schema, the importer generates a deterministic collision-safe fallback instead of producing invalid PostgreSQL DDL. Generated fallback names remain ASCII and bounded to the PostgreSQL identifier limit.

The parser remains intentionally bounded. Unsupported index expressions, malformed settings, or indexes that reference columns not present in the imported table are skipped rather than inventing schema objects. Quoted column identifiers are accepted for the supported simple-column subset, and commas inside quoted or nested default expressions are not treated as top-level separators.

## Standards traceability

DBML defines `indexes { ... }` with single or multi-column entries and settings including `pk`, `unique`, `name`, and `type`. The implementation therefore treats those settings as source evidence rather than presentation metadata.

PostgreSQL treats an index as a schema relation: `CREATE INDEX` requires its name to be distinct from other relations in the same schema, and the index is created in the schema of its parent table. PostgreSQL also permits delimited identifiers and stores object names in the `name` type, whose default build provides 63 usable bytes. For supported explicit DBML names within that boundary, rewriting Unicode, whitespace, or case would change customer schema identity, so the importer quotes and preserves the source value.

PostgreSQL primary-key constraints carry schema meaning and automatically create the enforcing unique index. Materializing DBML `[pk]` as both a constraint and a separate unique index would therefore duplicate the physical index rather than preserve intent.

## Verification

`backend/tests/test_dbml_import.py` covers simple and composite indexes, explicit names and access methods, quoted identifiers containing `)`, state after an `indexes` block, schema-level relation/index collisions, `[pk]` conversion, nested default expressions, pathological input bounds, and exact preservation of a valid non-ASCII explicit PostgreSQL index identifier through DDL export.

The test-first regression for explicit identifier fidelity was committed before the production change. It expects `매출 지역 인덱스` to remain the exact snapshot `index_name` and to render as a quoted PostgreSQL identifier; the predecessor implementation instead normalized the value to an ASCII fallback.

## Operational boundary

This importer produces snapshot and DDL evidence; it does not execute DDL against a customer database. Downstream execution remains responsible for normal authorization, migration review, and transaction/`CONCURRENTLY` constraints. Import must fail closed for unsupported forms rather than broadening the accepted grammar without regression coverage.

## References

DBML. (n.d.). *DBML syntax*. Retrieved August 26, 2026, from https://dbml.dbdiagram.io/docs/

PostgreSQL Global Development Group. (2026). *PostgreSQL 18.6 documentation: CREATE INDEX*. https://www.postgresql.org/docs/18/sql-createindex.html

PostgreSQL Global Development Group. (2026). *PostgreSQL 18.6 documentation: CREATE TABLE*. https://www.postgresql.org/docs/18/sql-createtable.html

PostgreSQL Global Development Group. (2026). *PostgreSQL 18.6 documentation: SQL syntax*. https://www.postgresql.org/docs/18/sql-syntax.html
