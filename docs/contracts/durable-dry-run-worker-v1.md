# Durable dry-run worker contract v1

- **Contract version:** `durable-dry-run-worker/v1`
- **Capability status:** Partial
- **Implemented boundary:** deterministic attempt orchestration
- **Not implemented:** concrete sandbox/credential providers, deployment wiring,
  live apply, production acceptance

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
5. bounded lock, sandbox-statement and preflight-statement timeouts.

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
- attempt number.

It does not contain plan JSON, compiler-owned SQL, PostgreSQL major, base
digest, DSN or credential. The injected provider resolves and constrains the
stored connection identity outside this contract.

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
   handler, never through the provider request.
3. The existing `complete_isolated_dry_run` boundary verifies the result and
   derives only `live_preflight_running`.
4. Immediately before target access, the handler locks and reloads the run and
   plan again. Cancellation, version loss, identity drift, expiry or integrity
   failure prevents opening the live capability.
5. The live read-only capability is entered and the existing
   `execute_bound_live_preflight` core receives the verified plan directly.
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
- A cancellation or CAS loss between sandbox completion and target access must
  prevent the target capability from opening.

## Failure and evidence policy

Provider exceptions are replaced with fixed worker-boundary errors using
`from None`. Provider diagnostics, DSNs, credentials, SQL and row data are not
persisted or returned. Durable evidence continues to be canonicalized by the
existing migration-run transition functions.

## Explicit non-goals

This contract does not implement or prove:

- disposable sandbox provisioning, dependency materialization or egress
  isolation;
- target credential resolution, network route isolation or least-privilege
  deployment identity;
- application startup, queue registration or production worker operation;
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
- cancellation/state-version recheck before target access;
- bounded configuration rejection;
- rejection of non-contract terminal states.

Real deployment readiness additionally requires supported PostgreSQL-version
integration with concrete providers, network and credential isolation proof,
fault/restart recovery, operational telemetry and browser E2E. None is claimed
by this Partial contract.
