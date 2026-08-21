# ADR-0003: Evidence-first performance and Rust boundary

- Status: Accepted for the first capacity-profile slice
- Date: 2026-08-21
- Scope: benchmark workloads, SLO evidence, and CPU/GPU/Rust decisions

## Decision

Keep the current Python and TypeScript reference paths. Add deterministic,
value-free workload profiles before changing the implementation language or
adding GPU execution. Record p50/p95 latency, peak RSS, artifact size, and
environment metadata for each run; set customer-facing limits only from
repeated baselines on declared hardware.

The first runnable slice measures JSON encoding and Snowflake DDL export. The
remaining capture, persistence, diff, queue, API, and browser paths remain
explicitly unmeasured rather than being represented by invented targets.

## Rust/GPU gate

An ADR for a Rust/WASM/service kernel requires a measured CPU or security
hotspot, stable behavior and wire format, golden reference fixtures, a bounded
low-crossing interface, parity/fuzz/cancellation/rollback evidence, and a
material improvement to a declared SLO. GPU work requires the same evidence
plus a workload that benefits from parallel numeric execution. Schema metadata
and relationship layout do not meet that bar by assertion.

## Consequences

- Benchmark output is comparable across commits and contains no customer data.
- Release candidates can publish a reproducibility receipt without claiming an
  SLA.
- The current implementation remains independently deployable and submodule
  friendly.
- A later migration can be narrow and reversible because the Python/TypeScript
  path remains the golden reference.

## References

Gansner, E. R., Koutsofios, E., North, S. C., & Vo, K.-P. (1993). A technique
for drawing directed graphs. *IEEE Transactions on Software Engineering,
19*(3), 214–230. https://doi.org/10.1109/32.221135

National Institute of Standards and Technology. (2022). *Secure software
development framework (SSDF) version 1.1* (NIST Special Publication 800-218).
https://doi.org/10.6028/NIST.SP.800-218

PostgreSQL Global Development Group. (2026). *PostgreSQL 18 documentation:
Table partitioning*. https://www.postgresql.org/docs/18/ddl-partitioning.html
