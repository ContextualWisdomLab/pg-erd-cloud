# ADR-0003: PostgreSQL Job Queue Authority

- Status: Accepted
- Lifecycle: `implemented_on_main`
- Date: 2026-08-09
- Supersedes: none

## Context

Queued snapshot work must survive API restarts and support multiple workers
without two workers claiming the same queued item. The application already
depends on PostgreSQL for tenant metadata and snapshot state. An optional
Valkey integration can reduce polling latency, but a wake-up message can be
lost or delivered more than once. The current worker has no lease, heartbeat,
watchdog, or reclaim transition, so a crash after claim can leave both queue
and snapshot rows in `running` indefinitely.

## Decision

`job_queue` in application PostgreSQL is the durable source of truth. Workers
claim eligible queued rows with a short transaction and `FOR UPDATE SKIP
LOCKED`, then record terminal state back in PostgreSQL. Valkey is an optional
wake signal; its contents never determine whether a job exists or completed.

Queued-work durability and concurrent claim exclusivity are implemented.
In-flight crash recovery, bounded retry, idempotent replay, leases/heartbeats,
and dead-letter handling are `planned` and must be added before the queue is an
acceptable production DDL executor.

## Alternatives considered

- Valkey as the authoritative queue: rejected because it adds a second durable
  state authority and reconciliation path for the present workload.
- In-memory background tasks: rejected because process loss loses work.
- Blocking row locks: rejected because idle workers would contend instead of
  skipping rows already claimed by peers.

## Consequences

- PostgreSQL availability bounds queue availability.
- Queue retention, lease recovery, idempotency, dead-letter policy, and
  telemetry must be explicit before using the queue for production Forward
  Engineering.
- The current snapshot queue design is not, by itself, authorization evidence
  for DDL execution.

## Verification

- Worker tests cover claim exclusivity and the currently implemented state
  transitions.
- Production monitoring of queue age, attempts, failures, worker health, stuck
  `running` rows, and Valkey degradation is `planned`; current observability
  hooks do not prove complete alert coverage.
- The Forward Engineering design extends rather than silently reinterprets
  this authority.

## References

See PostgreSQL Global Development Group (2026) in
[`docs/references.md`](../references.md).
