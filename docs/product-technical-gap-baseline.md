# pg-erd-cloud product and technical gap baseline

This file binds active product and technical gaps to exact repository evidence.
Entries are snapshots, not merge authorization; current exact-head Checks and
independent review must be fetched again before promotion.

| Gap ID | Status | Exact evidence | Action and acceptance boundary |
|---|---|---|---|
| `PG-ERD-FRONTEND-TEST-TOOLCHAIN-01` | Proposed — source repair under exact-head verification | PR `#1242@cb1be77b2209dcf1919a94d62efe2393c7c32940`; CI run `36668767330`, frontend job `109739048510`, failed `npm ci` because `vitest@5.0.2` conflicted with the exact `vitest@4.1.10` peer of `@vitest/coverage-v8@4.1.10`. Lock validation also found High advisories in `nanoid<3.3.18` and `undici<=8.10.1`; the repaired graph resolves 3.3.19 and 8.11.2 and reports zero npm audit findings. | Keep the Vitest runtime/coverage family atomic, prove manifest and lock agreement with a repository contract, and admit a future Vitest 5 migration only after DOM matcher type compatibility plus full frontend and hosted gates. |
| `PG-ERD-FRONTEND-COVERAGE-01` | Open — measured, not waived | Node 26 local V8 report after the toolchain repair: 1,518/1,521 statements, 1,143/1,151 branches, 320/321 functions, and 1,373/1,374 lines. | Add behavior-first tests for the remaining `App.tsx`, modal, and Prisma branches without exclusions, threshold reduction, synthetic production data, or source-only ignore directives. |
| `PG-ERD-HTTPX2-MIGRATION-01` | Open — upstream deprecation evidence preserved | Python 3.12 backend suite: 380 passed, 1 skipped, with one `StarletteDeprecationWarning` stating that `starlette.testclient` now requires `httpx2` rather than `httpx`. | Migrate the canonical backend lock and TestClient boundary to the released `httpx2` contract in a dedicated RED→GREEN change; do not filter the warning or mix the runtime migration into the frontend dependency repair. |
