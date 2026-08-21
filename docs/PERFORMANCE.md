# Performance and capacity profile

Status: benchmark contract established; no production SLO or SLA is claimed.

This repository now has a deterministic, value-free workload generator under
`benchmarks/`. It is a measurement tool only: generated names and metadata must
never be imported into a customer or production database.

## Profiles

| Profile | Schemas | Tables/views | Columns | FK edges | Indexes | Snapshots/project |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| small | 5 | 100 | 2,000 | 200 | 300 | 20 |
| medium | 25 | 1,000 | 25,000 | 3,000 | 5,000 | 100 |
| large | 100 | 10,000 | 250,000 | 30,000 | 50,000 | 500 |

Every profile accepts a seed and one of `baseline`, `dense_fk`, `deep_chain`,
`disconnected`, or `long_names`. The generator preserves exact cardinalities,
uses two-word synthetic identifiers, and emits no customer values.

## Reproducible run

From the repository root:

```bash
python benchmarks/run_capacity_benchmark.py \
  --profile small --variant baseline --seed 7 --repetitions 3 \
  > /tmp/pg-erd-capacity-manifest.json
```

The manifest records the commit, Python/platform metadata, object counts, JSON
size, and p50/p95 wall-clock measurements for JSON encoding and Snowflake DDL
export. It does not invent thresholds: release targets must be set after
baseline runs on declared hardware and container images.

Run the generator alone when an artifact is needed for a specific profile:

```bash
python benchmarks/capacity_profile.py \
  --profile medium --variant dense_fk --seed 7 \
  --output /tmp/pg-erd-medium.json
```

## Measurement boundary

The first slice measures pure serialization and DDL export. Introspection,
database persistence, diff/migration compilation, queue fairness, API
pagination, browser rendering, and OpenTelemetry dashboards remain release
work, not hidden claims. A future benchmark workflow must publish the same
manifest fields plus query count, I/O, lock wait, browser heap, long tasks,
frame time, cancellation time, and exact container metadata.

## Rust decision gate

Python/TypeScript remains the reference implementation until a profile shows a
production CPU or security hotspot. A Rust/WASM/service boundary is justified
only after the algorithm and wire contract are stable, golden parity fixtures
exist, the boundary avoids per-row crossings, cancellation and observability
are proven, and the result materially improves a declared SLO. GPU execution
is not presumed for schema metadata or graph layout without measurements.
