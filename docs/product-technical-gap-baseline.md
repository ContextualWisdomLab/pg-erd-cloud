# Product Technical Gap Baseline

## Backend schema export grouping allocation

- **Bounded Context / owner:** pg-erd-cloud schema export and ORM code generation.
- **Gap:** Mutable-default `dict.setdefault` created an unused list or set whenever an existing grouping key was seen.
- **Implemented delta:** PR #1136 replaces those calls in `backend/app/ddl/export.py` and `backend/app/spec/orm_codegen.py` with explicit key checks. For N accepted rows and U distinct keys, the bounded avoided temporary-collection count is at most `N−U`; algorithmic complexity remains Θ(N).
- **Evidence:** Exact output fixtures cover Prisma, TypeORM, SQLAlchemy, and DDL generation. Hosted CI run 34703495761 exposed an unconfigured third-party `benchmark` fixture after 382 tests passed; the fixture dependency was removed at `b12cd5cf0c7a18b7af340255548e117c8f5c804e`.
- **Action / acceptance:** Run paired baseline/current measurements on the same realistic snapshot and environment, reporting CPU, allocation, and GC median·p95. Do not claim performance improvement from current-only timings. Keep generated-schema semantic defects routed to their canonical repair PR rather than blessing them as optimization behavior.
- **Status:** Proposed — exact-head hosted checks and paired performance evidence remain pending.
