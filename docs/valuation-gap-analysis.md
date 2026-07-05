# pg-erd-cloud — Value Gap Analysis & Roadmap

_Grounded in a full code-knowledge-graph pass (147 files, 1,202 nodes, 17 communities,
61 flows) plus the live test suites (backend 258 pytest, frontend 136 vitest, `tsc` clean)._

## 1. What exists today (the moat we already have)

The codebase is a **schema-intelligence platform**, not just an ERD drawer. The graph
communities map cleanly to real capabilities:

| Capability | Module (community) | State |
| --- | --- | --- |
| Multi-dialect introspection | `pg_introspect`, `snowflake_introspect` | Solid, SSRF-guarded, 100% guard coverage |
| Structural diff (oid-independent) | `diff/schema_diff` | Solid, name-keyed |
| Dialect-aware DDL export | `ddl/export` | PG + Snowflake, type-mapped |
| **Migration SQL from diff** | `ddl/migration` | **NEW — this PR** |
| Reverse-engineering / index & cardinality advice | `spec/*` | LLM-assisted |
| AuthN/Z, RBAC, CSRF, DSN encryption, IDOR guards | `app` (auth) | Security-reviewed |
| Snapshots, saved views, table annotations, connection test, share links | `api/*` | Complete backend+frontend |
| ERD editor UI | `src/*`, `modals/*` | React + xyflow |

The security posture (SSRF host-pinning, IDOR uniform-404, encrypted DSN at rest,
DSN-redacted errors) is genuinely strong and is a differentiator for enterprise buyers.

## 2. Value thesis

A schema tool becomes a *platform teams pay for* when it moves up the value ladder:
**visualize → diff → _act_ → govern → automate**. We are strong on visualize/diff and
now cross into **act** (migration SQL). The gaps below are ordered by value-per-effort.

## 3. Prioritized gaps

### P0 — Actionability (turns insight into change teams pay for)
- **✅ Migration SQL from diff** _(delivered in this PR)_ — `GET /api/snapshots/{uuid}/migration.sql?against=…&dialect=…`. Diff two snapshots and get the `CREATE`/`ALTER`/`DROP` + FK statements to apply. Bridges the previously-disconnected `diff` and `ddl` modules the graph flagged.
- **✅ Migration safety review** _(delivered)_ — `GET /api/snapshots/{uuid}/migration-safety?against=…` classifies every change as **safe / warning / destructive** with a plain-language reason (drop = data loss; type change / `SET NOT NULL` / new FK = lock or fail against real data) plus a summary (`has_destructive`, `has_blocking`). Directly targets the #1 reason teams fear migrations.
- **CI drift check** — a documented `GET .../migration.sql` recipe + exit-code semantics so teams can gate deploys on "no unexpected drift."

### P1 — Breadth & documentation (expands addressable market)
- **More dialects** — MySQL / SQL Server / BigQuery / Redshift introspection. Each ~doubles the reachable market; needs a live instance per dialect for integration tests (flag as infra-gated).
- **Data dictionary export** — Markdown/HTML doc of schema + **annotations** (now that annotations exist) + PK/FK/index. High value for the "living documentation" buyer; pure-logic, testable.
- **Relationship inference** — suggest implicit FKs by naming/type heuristics (`*_id` → `id`). Composes with existing cardinality logic.

### P2 — Scale, governance, monetization (justifies a valuation, not just a product)
- **Robust async jobs** — `jobs` is DB-queue MVP; harden the valkey worker path (retries/backoff/idempotency) for large-schema introspection at scale.
- **Audit log + org multi-tenancy + usage quotas** — table-stakes for enterprise/SOC2 and for billing.
- **Observability SLOs** — `observability.py` exists; add per-tenant metrics + alerting.
- **Public API keys / SDK** — programmatic snapshots & diffs enable CI/CD integrations (the stickiest use case).

## 4. Delivered in this PR

`ddl/migration.py` — `snapshot_diff_to_migration_sql(base, target, dialect)`:
- name-based matching (never volatile `relation_oid`),
- reuses `diff/schema_diff` indexing + `ddl/export` type-mapping/quoting,
- emits CREATE / DROP / ADD·DROP·ALTER COLUMN / SET·DROP NOT NULL / ADD·DROP FOREIGN KEY,
- destructive & PK changes emitted with review comments,
- PostgreSQL-precise, Snowflake `SET DATA TYPE` handling,
- endpoint `GET /api/snapshots/{uuid}/migration.sql` (IDOR-safe, dialect param),
- 7 unit tests incl. oid-independence.

Next (Loop): data-dictionary export (P1) and CI drift recipe (P0).
