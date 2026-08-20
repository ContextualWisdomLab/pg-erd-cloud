# ADR-0003: Keep the job-queue hot working set bounded

- **Status:** Accepted
- **Date:** 2026-08-20
- **Scope:** PostgreSQL-backed `job_queue` claim path

## Decision

Add a PostgreSQL partial B-tree index on `(run_after, job_queue_uuid)` for rows
whose `status = 'queued'`, and claim jobs in that same deterministic order.
This keeps terminal job history out of the worker's hot access path while
preserving `FOR UPDATE SKIP LOCKED` and the existing PostgreSQL source of
truth. The migration is stacked after the ORM/migration reconciliation in
PR #936 so the Alembic chain remains linear.

This is hot-partition readiness, not a claim that every table should be
partitioned. The queue is the append-heavy, repeatedly scanned table. When
queue volume or wait-time SLO evidence crosses the documented operating
threshold, introduce time-range partitions with a retention/rollover plan;
do not create speculative partitions for low-write metadata tables.

## Consequences

- Queued rows have a smaller index working set as succeeded and failed history
  accumulates.
- The predicate exactly matches the worker query, making the intended access
  path planner-visible.
- The stable UUID tie-breaker prevents arbitrary ordering among jobs with the
  same `run_after` timestamp.
- A future partition migration must preserve the claim contract, retention
  evidence, rollback path, and real PostgreSQL upgrade/downgrade tests.

## Evidence

- `backend/tests/test_hot_queue_index.py` verifies the ORM contract.
- `0009_hot_queue_claim_index.py` verifies the deployable migration contract.
- `docs/observability.md` defines queue wait and failure thresholds that can
  trigger a measured partitioning decision.
