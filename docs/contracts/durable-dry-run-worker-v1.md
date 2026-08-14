# Durable dry-run worker contract v1

- **Contract version:** `durable-dry-run-worker/v1`
- **Capability status:** Partial
- **Implemented boundary:** deterministic attempt orchestration and a
  provider-callable metadata handoff guard
- **Not implemented:** concrete sandbox/credential providers, deployment wiring,
  live apply or production readiness

## Purpose

This contract binds one UUID-only migration-run signal and one exact durable
`MigrationRunAttemptClaim` to the existing isolated PostgreSQL dry-run and live
read-only preflight cores. It does not grant arbitrary SQL or apply authority.

`make_durable_dry_run_attempt_handler` returns the
`MigrationRunAttemptHandler` consumed by the existing dual-lease consumer. The
consumer remains responsible for the Valkey signal lease and durable attempt
heartbeat. The handler remains responsible for server-authoritative metadata,
capability sequencing and durable result transitions.

## Authority inputs

The handler accepts only:

1. a server-owned `SessionFactory`;
2. a UUID-only `MigrationRunSignalClaim`;
3. an exact `MigrationRunAttemptClaim` containing the durable attempt UUID,
   run UUID, attempt number and acquired state version;
4. injected `IsolatedSandboxFactory` and `LivePreflightFactory` capabilities;
5. bounded lock and statement timeouts plus whole-stage sandbox and preflight
   cancellation deadlines.

A signal/run UUID mismatch fails before metadata or provider access.

### Sandbox capability request

`IsolatedSandboxRequest` contains only:

- run, plan, project, base-snapshot and exact attempt UUIDs;
- attempt number;
- PostgreSQL major version;
- expected base digest.

It does not contain a target connection UUID, target digest, plan JSON,
compiler-owned SQL, DSN or credential.

### Live-preflight capability request

`LivePreflightRequest` contains only:

- run, plan, project, stored target-connection and exact attempt UUIDs;
- attempt number and the exact expected run state version refreshed immediately
  before provider access.

It does not contain plan JSON, compiler-owned SQL, PostgreSQL major, base
digest, DSN or credential. The injected provider resolves and constrains the
stored connection identity outside this contract.

`guard_live_preflight_handoff` is a server-owned, provider-callable check. In
one fresh database statement it matches the exact run, plan, project, stored
target, attempt UUID, attempt number and expected run state version. The same
statement requires an active unexpired attempt, uncancelled
`live_preflight_running` state, matching run/plan digest and an unexpired plan.
It returns no credential, route, connection, plan JSON or SQL. Driver/query
failures and non-matches expose only the fixed handoff error.

The PostgreSQL 14–18 matrix exercises this statement through the test-owned
provider before its target connection, proves the exact lease-expiry boundary
fails closed after an interrupted first attempt, and then accepts the exact
successor attempt. This is ephemeral database evidence, not deployed provider
composition.

## Server-authoritative metadata checks

Before external I/O, the handler locks and reloads the exact run and immutable
plan and rejects any mismatch in:

- run kind, state, state version or cancellation flag;
- run, plan, project, snapshot and target-connection identities;
- exact durable attempt UUID and attempt number;
- plan digest, compiler version, base digest and target digest;
- plan expiry, PostgreSQL major, `can_dry_run` or blockers.

The plan JSON is deep-copied through canonical JSON before use. The existing
plan digest verifier remains authoritative.

## State and execution sequence

1. `queued` is advanced by CAS to `sandbox_running` using the existing
   `sandbox_started` event. Evidence contains only the attempt number and exact
   durable attempt UUID.
2. The isolated capability is entered and the existing
   `execute_isolated_dry_run` core receives the verified plan directly from the
   handler, never through the provider request. One whole-stage cancellation
   deadline covers provider acquisition, execution and snapshot capture, then
   requests task cancellation and awaits capability cleanup.
3. The existing `complete_isolated_dry_run` boundary verifies the result and
   derives only `live_preflight_running`.
4. Immediately before target access, the handler locks and reloads the run and
   plan again. Cancellation, version loss, identity drift, expiry or integrity
   failure prevents opening the live capability.
5. The live read-only request carries the exact refreshed run state version.
   A concrete provider can call `guard_live_preflight_handoff` immediately
   before resolving the stored target to recheck the full identifier/state/
   lease tuple in one fresh database statement. The live capability is then
   entered and the existing
   `execute_bound_live_preflight` core receives the verified plan directly.
   A separate whole-stage cancellation deadline covers reader acquisition,
   capture and checks, then requests cancellation and awaits cleanup.
6. The existing `complete_live_preflight` boundary derives only `passed`,
   `drifted` or `failed`.

## Restart and cancellation

- A claimed attempt may resume from `sandbox_running`.
- A claimed attempt may resume from `live_preflight_running` without replaying
  an already completed sandbox.
- Other states fail closed.
- `asyncio.CancelledError`, `KeyboardInterrupt` and `SystemExit` propagate.
- Both injected async context managers must close on success, failure and
  cancellation.
- Provider acquisition, snapshot callbacks and async-context cleanup must use
  cooperative cancellation: they must not suppress `CancelledError` or block
  indefinitely after cancellation is requested. The in-process
  `asyncio.wait_for` boundary does not prove a hard wall-clock termination
  bound for a non-conforming provider. Process isolation and an external kill
  boundary remain deployment requirements before worker operation can be
  considered bounded against a hung provider.
- If handler completion and heartbeat termination become observable in the
  same scheduler turn, the handler result proceeds first to the exact-attempt
  completion CAS and then to exact signal acknowledgement. Those CAS
  operations remain authoritative: an expired, replaced or otherwise lost
  owner still fails closed and cannot authorize acknowledgement.
- The current post-sandbox reload narrows the cancellation/lease-loss window,
  and its identifier-only request now carries the exact expected run state
  version. The provider-callable guard atomically revalidates cancellation,
  that state version, stored identities and the exact active attempt lease in
  one database statement. No concrete provider is wired to it, and even when
  composed it does not eliminate the gap between that metadata observation and
  target capability opening. Provider composition, credential/route binding
  and cancellation after the observation remain Planned and release-blocking.

## Failure and evidence policy

Provider exceptions are replaced with fixed worker-boundary errors using
`from None`. Provider diagnostics, DSNs, credentials, SQL and row data are not
persisted or returned. Whole-stage deadline expiry requests cancellation of
the in-flight capability coroutine, awaits async-context cleanup and emits the
same fixed stage failure when cooperative cancellation completes. This is
timeout cancellation and capability cleanup evidence for conforming test
providers only; it does not prove a hard wall-clock termination bound. This
includes durable-attempt and signal-heartbeat
renewal failures; both cancel and retrieve in-flight work before exposing only
their fixed lease-loss error. Durable evidence continues to be canonicalized
by the existing migration-run transition functions.

## Explicit non-goals

This contract does not implement or prove:

- disposable sandbox provisioning, dependency materialization or egress
  isolation;
- target credential resolution, network route isolation or least-privilege
  deployment identity;
- application startup, queue registration or production worker operation;
- forcible termination of a provider that suppresses cancellation, or the
  deployed process-supervisor kill boundary;
- apply dispatch, DDL execution, apply-time drift/CAS, recovery or convergence;
- PostgreSQL/Valkey deployment acceptance or accessible browser E2E.

## Acceptance families

Repository tests must cover:

- exact attempt and provider-request field binding;
- sandbox then live-preflight ordering and cleanup;
- restart without sandbox replay;
- metadata integrity and queued CAS event evidence;
- claim mismatch before metadata access;
- cancellation propagation and provider-error redaction;
- sandbox/live whole-stage timeout cancellation and capability cleanup for
  cooperative providers;
- cancellation/state-version recheck before target access;
- bounded configuration rejection;
- rejection of non-contract terminal states.

Real deployment readiness additionally requires supported PostgreSQL-version
integration with concrete providers, network and credential isolation proof,
fault/restart recovery, operational telemetry and browser E2E. None is claimed
by this Partial contract.
