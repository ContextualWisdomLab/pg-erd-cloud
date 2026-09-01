# Performance & capacity profile

Status: **in progress** — first increment (workload generators) landed.
Tracks issue
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

## Deferred (later increments on #951)

- **Baseline harness** — run the measured paths (canonical snapshot
  hashing, JSON encode/decode + persistence, schema diff, DDL/DBML/Mermaid/
  Prisma/spec export, API list/detail/pagination/search, queue
  claim/retry/lease/cleanup/fairness) against each profile and record
  p50/p95/p99 latency, peak RSS, allocations, query count, lock wait, queue
  lag, artifact size, cancellation time.
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
