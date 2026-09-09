# Performance & capacity profile

Status: **in progress** — increments 1 (workload generators), 2 (measured
baseline harness), 3 (repeat-run aggregation), and 4 (versioned report
envelope) landed. Tracks issue
[#951](https://github.com/ContextualWisdomLab/pg-erd-cloud/issues/951)
("[Performance Gap] Establish large-schema SLOs, workload benchmarks, and a
measured Rust boundary").

## Why

pg-erd-cloud has no published capacity envelope. A buyer cannot tell whether
100, 1,000, or 10,000 tables stay usable, how much memory a snapshot/export
costs, or where a Rust rewrite would actually help. Rewriting Python by
assertion adds risk without evidence — a reproducible workload model and
measured baselines must come first.

## Decision — deterministic workload generators (this increment)

`app/perf/workload_profiles.py` generates schema snapshots in the common
introspection JSON shape at three named sizes and a set of skew cases.

| Profile | Schemas | Relations | Columns | FK edges | Indexes | Snapshots/project |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `small` | 5 | 100 | 2,000 | 200 | 300 | 20 |
| `medium` | 25 | 1,000 | 25,000 | 3,000 | 5,000 | 100 |
| `large` | 100 | 10,000 | 250,000 | 30,000 | 50,000 | 500 |

Counts match issue #951 exactly (`generate_workload_snapshot(profile)`).

Skew builders: `wide_relation_snapshot` (one 5,000-column relation),
`dense_fk_cluster_snapshot`, `deep_dependency_chain_snapshot`,
`disconnected_components_snapshot`, `multilingual_identifier_snapshot`
(quoted/non-ASCII names + large comments), `partition_hierarchy_snapshot`.

Guarantees:

* **Deterministic** — every generator takes a `seed` (a per-profile default
  when omitted) and returns byte-for-byte identical output for that seed.
* **Anonymized** — identifiers are built from a fixed synthetic vocabulary;
  no real customer / person / organization names, no production data values.
* **No thresholds** — the module is generators only. Latency, throughput, and
  memory targets are set from measured baseline runs, never invented here.
* DB object names follow the project rule: two-or-more-word `snake_case`
  (except the deliberately non-ASCII / quoted identifiers in the multilingual
  skew case).

## Decision — measured baseline harness (this increment)

`app/perf/baseline.py` times the *pure*, side-effect-free processing paths
over a generated workload snapshot and records observations only — no
threshold, no verdict.

`run_baseline(profile_name, *, seed=None)` returns `profile`, `seed`,
`generated_at` (UTC ISO-8601), `relation_count`, `column_count`, and a
`paths` map. Each path reports `wall_seconds`, `peak_bytes` (via
`tracemalloc`), and `result_size_bytes`. Measured paths:

| Path | What it exercises |
| --- | --- |
| `canonical_hash` | `sha256` over sorted-key canonical JSON |
| `json_round_trip` | `json.dumps` + `json.loads` of the snapshot |
| `schema_self_diff` | `app.diff.schema_diff.diff_snapshots(s, s)` |
| `ddl_export_postgresql` | `app.ddl.export.snapshot_json_to_sql(s, "postgresql")` |
| `ddl_export_snowflake` | `app.ddl.export.snapshot_json_to_sql(s, "snowflake")` |
| `data_dictionary_markdown` | `app.spec.data_dictionary.snapshot_to_data_dictionary_md(s)` |

CLI: `python -m app.perf.baseline --profile small [--seed N] [--json]`.
`tracemalloc` is torn down in a `finally` block, so a cancelled run leaves
no tracing active and never returns a partial report.

## Decision — repeat-run aggregation (this increment)

A single timing is noisy. `app/perf/baseline_stats.py` runs `run_baseline`
`repeat` times over the *same* seeded workload (snapshot fixed; only the
timing varies) and reduces each path's `wall_seconds` and `peak_bytes`
sample lists to a distribution summary — `samples`, `min`, `max`, `mean`,
`p50`, `p95`, `p99` — via `statistics.quantiles(..., n=100,
method="inclusive")` (standard library only). `result_size_bytes` is
deterministic for a fixed snapshot, so it is reported once as a scalar.

`aggregate_baseline(profile_name, *, repeat, seed=None)` adds `repeat` to
the report metadata. `repeat < 1` raises `ValueError`; `repeat == 1`
returns a well-formed degenerate summary (every quantile equals the one
sample). A cancelled aggregation never returns a partial distribution.
CLI: `python -m app.perf.baseline_stats --profile small --repeat 5
[--seed N] [--json]`.

Still observations only: no threshold, no verdict. The percentile targets
a capacity profile eventually publishes are set from measured baseline
runs and never invented here.

## Decision — versioned report envelope (this increment)

`app/perf/baseline_report.py` `build_baseline_report(profile_name, *,
repeat, seed=None)` wraps the raw `aggregate_baseline` output in a
buyer-facing envelope, mirroring what `app.spec.normalization_report`
(#947) does for the normalization assessment: `report_version`,
`generated_at` (UTC ISO-8601), a `schema_fingerprint` (`"sha256:"`-prefixed
digest of the exact workload snapshot that was measured, so a report can be
tied back to its schema), and a `summary` block —
`{headline, path_count, slowest_path_by_wall_p95}` — that names the path an
engineer should look at first (largest wall-time 95th percentile) using
**names and counts only, never a duration value**. The full statistics
block is preserved verbatim under `statistics`. The `schema_fingerprint`
helper is a local copy of `app.spec.normalization_report.schema_fingerprint`
for now (the two branches are unmerged); unify them once both land.

## Deferred (later increments on #951)

- **Baseline harness — remaining paths** — DBML/Mermaid/Prisma/spec export,
  API list/detail/pagination/search, and queue
  claim/retry/lease/cleanup/fairness, plus query count, lock wait, and
  queue lag. The pure snapshot paths above are done and their percentile
  aggregation is in place; these remaining paths need a DB / event loop and
  belong in the benchmark workflow.
- **`docs/PERFORMANCE.md`** — the versioned capacity profile with
  buyer-facing limits, separated from benchmark targets. **No SLA claim
  until production evidence exists.**
- **Benchmark workflow** — separate from ordinary PR correctness gates,
  required for release candidates, with an exact-current-head manifest and
  reproducibility receipt; flamegraphs stored as build artifacts, not
  committed binaries.
- **Frontend traces** — initial load, graph virtualization, search,
  selection, layout, zoom, export, saved-view restore, and 200%-zoom /
  constrained-memory interaction.
- **Rust decision gate** — per #951, an ADR per candidate hotspot (canonical
  snapshot normalization/hashing, schema-diff graph algorithms, identifier
  allocation, DBML/DDL parse/render, large relationship-aware layout). A Rust
  boundary is justified only when the path is a *measured* production
  CPU/security hotspot, the contract is stable, a language reference + golden
  fixtures exist, a bounded FFI/WASM/service interface avoids per-row
  crossing, and parity/fuzz/memory-safety/cancellation/rollback/observability
  are proven. Browser layout may use worker/WASM before any GPU path; GPU is
  not justified for these paths without evidence.

## References (APA 7th)

Gregg, B. (2020). *Systems performance: Enterprise and the cloud* (2nd ed.).
Addison-Wesley.

Molyneaux, I. (2014). *The art of application performance testing: From
strategy to tools* (2nd ed.). O'Reilly Media.

The PostgreSQL Global Development Group. (2025). *PostgreSQL 17 documentation:
Chapter 14, Performance tips*. https://www.postgresql.org/docs/17/performance-tips.html
