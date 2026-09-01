# Job queue semantic status naming

## Decision

The application-owned durable queue uses `job_status` as the authoritative queue-state name instead of the generic one-word `status`. The bounded context is the PostgreSQL-backed background job queue, so both the SQLAlchemy attribute and physical PostgreSQL column carry the queue meaning explicitly. The supporting claim-path index is correspondingly named `ix_job_queue__job_status_run_after`.

This is a semantic-specificity rule, not a casing rule. PostgreSQL-owned schema objects remain multiword `snake_case`; Python code follows Python naming conventions.

## Migration and compatibility boundary

Alembic revision `0008_job_queue_status_name` performs a PostgreSQL metadata rename from `job_queue.status` to `job_queue.job_status`. It renames the existing compound index rather than dropping and rebuilding it, so the `(job_status, run_after)` access path remains the same physical index and preserves the `FOR UPDATE SKIP LOCKED` claim strategy.

`ALTER TABLE ... RENAME COLUMN` takes an `ACCESS EXCLUSIVE` table lock while PostgreSQL updates catalog metadata. The production compose contract runs `alembic upgrade head` before the backend starts, so deployment must not leave an older worker concurrently processing `job_queue.status` while this migration is applied. A transitional SQLAlchemy synonym accepts historical Python `status=` construction while callers move to `job_status`; it does not recreate a physical `status` column.

The downgrade reverses both metadata names. There is no data rewrite, no new table, no foreign-key change, no change to row cardinality or functional dependencies, and therefore no 3NF change. No UPSERT path is introduced or altered. The queue remains a single PostgreSQL source of truth and the Valkey path remains a wake-up signal only.

## Concurrency and performance

The worker still claims due jobs with `FOR UPDATE SKIP LOCKED`, ordered by `run_after`. Renaming the existing index avoids an index rebuild and retains the same leading state predicate followed by schedule ordering. This change does not add a hot partition, change worker transaction boundaries, or change the read/write separation model.

## TDD evidence

The regression-first commit `1f6656f66bc4abb4be1ac6cc2779439eb357c31e` was created before production repair. It requires the physical `job_status` column, the qualified index name and ordering, raw claim SQL using `job_status`, and a reversible Alembic metadata/index rename. Production commits then update the worker, ORM and migration while preserving queue behavior.

Focused verification:

```bash
cd backend
PYTHONPATH=. pytest -q tests/test_job_queue_naming_contract.py
```

Repository verification remains the documented backend gate:

```bash
cd backend
PYTHONPATH=. mypy app
PYTHONPATH=. pytest -q
```

Exact-head GitHub checks, review threads and normal branch protection remain merge authority; predecessor or base evidence does not transfer.
