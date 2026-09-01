# Diagram view semantic identifiers

## Decision

`ContextualWisdomLab/pg-erd-cloud` owns the persisted Saved Diagram View contract. The database/ORM/Pydantic-owned display-name concept therefore uses the bounded-context name `diagram_name` rather than the generic one-word `name`. Casing follows each implementation surface; this change does not prohibit meaningful multiword camelCase or PascalCase identifiers elsewhere.

The existing HTTP JSON contract remains `{ "name": ... }` because it is already a customer-facing wire contract. Pydantic treats `name` as an explicit compatibility alias while organization-owned Python code reads and writes `diagram_name`. Read-only `name` properties preserve historical direct Python consumers without making the generic name authoritative.

## DDD boundary

**Bounded context:** Saved Diagram View, within pg-erd-cloud's ERD Collaboration product context.

**Aggregate:** `DiagramView`, identified by `diagram_view_uuid` and owned by `project_space_uuid`.

**Value objects / attributes:** `diagram_name`, `layout_json`, creator identity, and created/updated timestamps.

**Invariant:** organization-owned persistence and application code must not require a reader to infer what a bare `name` denotes; the saved-view display name is `diagram_name`. The external HTTP compatibility alias may remain `name` only at the API anti-corruption boundary.

**Domain events:** none are introduced by this refactor. Create/list/read/delete semantics are unchanged.

## Persistence, normalization, and migration

Alembic revision `0008_diagram_view_semantic_name` renames `diagram_view.name` to `diagram_view.diagram_name`. PostgreSQL documents that `ALTER TABLE ... RENAME` changes the catalog name without changing stored data. The operation normally takes an `ACCESS EXCLUSIVE` table lock, so the migration sets a transaction-local five-second `lock_timeout`; if the lock cannot be acquired promptly, deployment fails closed and can be retried after diagram-view traffic is quiesced rather than waiting indefinitely.

This is a metadata-only rename: no table rewrite, data copy, backfill, sequence change, index rebuild, or row-value transformation is performed. Downgrade reverses the column name under the same bounded lock-wait policy. The application deployment contract already runs `alembic upgrade head` before backend startup, so a new backend process never starts against the historical column name. Operators performing rolling multi-version deployment must drain old backend writers/readers before applying this revision because an old process that emits SQL for `name` cannot coexist after the catalog rename.

The relation remains in third normal form: `diagram_name` is a scalar fact fully dependent on `diagram_view_uuid`; the rename adds no repeating group, partial dependency, or transitive dependency. There is no UPSERT path for `DiagramView` in the current API: create inserts a new `diagram_view_uuid`, reads are project/member scoped, and delete removes the aggregate. The rename therefore does not alter conflict targets or UPSERT semantics. `diagram_view` is not used as a hot queue/partition key and this change adds no partitioning or new index. Existing project-space lookup/index behavior is unchanged.

## Compatibility and tests

`DiagramViewCreateIn` and `DiagramViewOut` make `diagram_name` authoritative and use the legacy wire alias `name`; serialization with aliases preserves the existing frontend/API payload. `backend/tests/test_diagram_view_naming_contract.py` asserts that the ORM table contains `diagram_name` but not `name`, that the Pydantic field model is semantic, and that wire serialization still emits `name`. Existing endpoint tests use `diagram_name` internally and also assert the legacy Python/wire compatibility view.

Fresh exact-head GitHub Checks remain merge authority. No predecessor/base status may be transferred to the final head.

## Research and standards traceability

Feitelson and colleagues show that program identifiers act as implicit documentation and that naming quality depends on selecting the concepts represented in a name. Schankin and colleagues found that descriptive compound identifiers can improve semantic code comprehension. Those findings support qualifying an organization-owned display name with its domain concept (`diagram_name`) rather than enforcing a casing style. PostgreSQL 18 is the operational authority for the catalog rename and lock-timeout behavior used by this migration.

Feitelson, D. G., Mizrahi, A., Noy, N., Ben Shabat, A., Eliyahu, O., & Sheffer, R. (2022). How developers choose names. *IEEE Transactions on Software Engineering, 48*(1), 37–52. https://doi.org/10.1109/TSE.2020.2976920

PostgreSQL Global Development Group. (2026). *PostgreSQL 18 documentation: ALTER TABLE*. https://www.postgresql.org/docs/18/sql-altertable.html

PostgreSQL Global Development Group. (2026). *PostgreSQL 18 documentation: Client connection defaults (`lock_timeout`)*. https://www.postgresql.org/docs/18/runtime-config-client.html

Schankin, A., Berger, A., Holt, D. V., Hofmeister, J. C., Riedel, T., & Beigl, M. (2018). Descriptive compound identifier names improve source code comprehension. In *Proceedings of the 26th Conference on Program Comprehension* (pp. 31–40). Association for Computing Machinery. https://doi.org/10.1145/3196321.3196332
