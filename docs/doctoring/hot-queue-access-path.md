# Hot queue access-path doctoring

This record explains the queue working-set decision in ADR-0003 and keeps the
research traceability next to the migration.

## Research-to-decision mapping

| Source | Applied decision |
|---|---|
| PostgreSQL Global Development Group (2026a) | Use a partial index whose predicate exactly matches `status = 'queued'`; do not assume a mathematically equivalent predicate will be recognized by the planner. |
| PostgreSQL Global Development Group (2026b) | Treat partitioning as a separate measured scale decision; a partial index is not a substitute for time-range partitioning when the table is large enough to require it. |

## Evidence

- `backend/app/models.py` and `0009_hot_queue_claim_index.py` define the same
  `(run_after, job_queue_uuid)` predicate-backed access path.
- `backend/tests/test_hot_queue_index.py` verifies the ORM metadata contract.
- A real PostgreSQL 16 migration run applied `0001` through `0009`, found the
  expected predicate index, downgraded `0009`, upgraded it again, and returned
  `alembic check: No new upgrade operations detected.`
- The existing p95 queue-wait alert (`> 60s for 10 minutes`) is the first
  operational signal for a future partition/retention design review.

## References (APA 7th)

PostgreSQL Global Development Group. (2026a). *11.8. Partial indexes*.
PostgreSQL 18.4 documentation. https://www.postgresql.org/docs/current/indexes-partial.html

PostgreSQL Global Development Group. (2026b). *5.12. Table partitioning*.
PostgreSQL 18.4 documentation. https://www.postgresql.org/docs/current/ddl-partitioning.html
