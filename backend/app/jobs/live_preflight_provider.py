"""Guarded stored-PostgreSQL provider for bounded live preflight only."""

from __future__ import annotations

import asyncio
import math
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from app.forward.migration_run import MigrationRunAttemptClaim
from app.jobs.migration_dry_run_worker import (
    LivePreflightExecution,
    LivePreflightRequest,
    MigrationDryRunWorkerError,
    load_guarded_live_preflight_target,
    make_durable_dry_run_attempt_handler,
)
from app.jobs.migration_dry_run_worker_contract import (
    IsolatedSandboxFactory,
    LivePreflightFactory,
    SessionFactory,
)
from app.jobs.migration_run_consumer import (
    MigrationRunAttemptHandler,
    MigrationRunHandler,
    make_attempt_bound_migration_run_handler,
)
from app.jobs.valkey_queue import MigrationRunSignalClaim
from app.pg_introspect.introspect import (
    capture_postgres_snapshot,
    connect_guarded_postgres,
)
from app.security import decrypt_text

__all__ = [
    "make_stored_postgres_durable_dry_run_attempt_handler",
    "make_stored_postgres_live_preflight_factory",
    "make_stored_postgres_migration_run_handler",
]

_CONNECT_TIMEOUT_SECONDS = 10.0
_MAX_CONNECT_TIMEOUT_SECONDS = 60.0


def _provider_error() -> MigrationDryRunWorkerError:
    """Return the one non-reflecting provider acquisition error."""

    return MigrationDryRunWorkerError(
        "migration live-preflight provider failed"
    )


def make_stored_postgres_live_preflight_factory(
    session_factory: SessionFactory,
    *,
    connect_timeout_seconds: float = _CONNECT_TIMEOUT_SECONDS,
) -> LivePreflightFactory:
    """Compose exact stored metadata with the guarded PostgreSQL connector.

    The returned capability decrypts only after the single-query live-attempt
    guard succeeds, pins the connection through the existing DNS/SSRF/TLS
    boundary, repeats the exact guarded-target lookup after connection open,
    scopes snapshot capture to that exact connection, and always closes it.
    It grants no arbitrary-SQL or apply authority and is not wired into
    application startup.
    """

    if not callable(session_factory):
        raise ValueError("live-preflight session factory is invalid")
    if (
        isinstance(connect_timeout_seconds, bool)
        or not isinstance(connect_timeout_seconds, (int, float))
        or not math.isfinite(connect_timeout_seconds)
        or not 0.0 < connect_timeout_seconds <= _MAX_CONNECT_TIMEOUT_SECONDS
    ):
        raise ValueError(
            "live-preflight connect timeout must be greater than 0 "
            "and at most 60 seconds"
        )
    bounded_connect_timeout_seconds = float(connect_timeout_seconds)

    @asynccontextmanager
    async def stored_postgres_live_preflight(
        request: LivePreflightRequest,
    ) -> AsyncIterator[LivePreflightExecution]:
        try:
            async with session_factory() as session:
                target = await load_guarded_live_preflight_target(
                    session, request
                )
            dsn = decrypt_text(target.dsn_ciphertext, target.dsn_nonce)
            connection = await connect_guarded_postgres(
                dsn, timeout=bounded_connect_timeout_seconds
            )
        except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
            raise
        except Exception:  # noqa: BLE001
            raise _provider_error() from None

        async def capture_exact_connection(
            capture_connection: asyncpg.Connection,
        ) -> dict:
            if capture_connection is not connection:
                raise MigrationDryRunWorkerError(
                    "live-preflight capture connection is invalid"
                )
            return await capture_postgres_snapshot(
                capture_connection, target.schema_filter
            )

        body_failed = False
        try:
            try:
                async with session_factory() as session:
                    revalidated_target = (
                        await load_guarded_live_preflight_target(
                            session, request
                        )
                    )
                if revalidated_target != target:
                    raise _provider_error()
            except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
                raise
            except Exception:  # noqa: BLE001
                raise _provider_error() from None

            yield LivePreflightExecution(
                connection=connection,
                capture_snapshot=capture_exact_connection,
            )
        except BaseException:
            body_failed = True
            raise
        finally:
            try:
                await connection.close()
            except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
                raise
            except Exception:  # noqa: BLE001
                if not body_failed:
                    raise _provider_error() from None

    return stored_postgres_live_preflight


def make_stored_postgres_durable_dry_run_attempt_handler(
    session_factory: SessionFactory,
    sandbox_factory: IsolatedSandboxFactory,
    *,
    lock_timeout_ms: int = 1_000,
    sandbox_statement_timeout_ms: int = 30_000,
    preflight_statement_timeout_ms: int = 5_000,
    sandbox_stage_timeout_seconds: float = 300.0,
    preflight_stage_timeout_seconds: float = 30.0,
    connect_timeout_seconds: float = _CONNECT_TIMEOUT_SECONDS,
) -> MigrationRunAttemptHandler:
    """Bind the stored-target provider to one durable metadata authority.

    The caller still injects isolated sandbox lifecycle and must explicitly
    wire the returned attempt handler into a consumer.  The identity check
    prevents that consumer from supplying a different session factory for run
    state while the live provider resolves credential-bearing target metadata.
    This composition grants no startup, arbitrary-SQL, or apply authority.
    """

    live_preflight_factory = make_stored_postgres_live_preflight_factory(
        session_factory,
        connect_timeout_seconds=connect_timeout_seconds,
    )
    durable_handler = make_durable_dry_run_attempt_handler(
        sandbox_factory,
        live_preflight_factory,
        lock_timeout_ms=lock_timeout_ms,
        sandbox_statement_timeout_ms=sandbox_statement_timeout_ms,
        preflight_statement_timeout_ms=preflight_statement_timeout_ms,
        sandbox_stage_timeout_seconds=sandbox_stage_timeout_seconds,
        preflight_stage_timeout_seconds=preflight_stage_timeout_seconds,
        connect_timeout_seconds=connect_timeout_seconds,
    )

    async def handle_stored_postgres_attempt(
        attempt_session_factory: SessionFactory,
        signal_claim: MigrationRunSignalClaim,
        attempt_claim: MigrationRunAttemptClaim,
    ) -> None:
        if attempt_session_factory is not session_factory:
            raise MigrationDryRunWorkerError(
                "migration dry-run composition is invalid"
            )
        await durable_handler(
            attempt_session_factory, signal_claim, attempt_claim
        )

    return handle_stored_postgres_attempt


def make_stored_postgres_migration_run_handler(
    session_factory: SessionFactory,
    sandbox_factory: IsolatedSandboxFactory,
    *,
    worker_identity: str,
    attempt_lease_seconds: int = 60,
    heartbeat_interval_s: float | None = None,
    lock_timeout_ms: int = 1_000,
    sandbox_statement_timeout_ms: int = 30_000,
    preflight_statement_timeout_ms: int = 5_000,
    sandbox_stage_timeout_seconds: float = 300.0,
    preflight_stage_timeout_seconds: float = 30.0,
    connect_timeout_seconds: float = _CONNECT_TIMEOUT_SECONDS,
) -> MigrationRunHandler:
    """Bind the stored dry-run capability to durable attempt leasing.

    The returned execution-neutral handler can be injected into the existing
    UUID-only signal consumer.  This composition does not start that consumer,
    provision a sandbox, accept SQL, or grant apply authority.
    """

    attempt_handler = make_stored_postgres_durable_dry_run_attempt_handler(
        session_factory,
        sandbox_factory,
        lock_timeout_ms=lock_timeout_ms,
        sandbox_statement_timeout_ms=sandbox_statement_timeout_ms,
        preflight_statement_timeout_ms=preflight_statement_timeout_ms,
        sandbox_stage_timeout_seconds=sandbox_stage_timeout_seconds,
        preflight_stage_timeout_seconds=preflight_stage_timeout_seconds,
    )
    return make_attempt_bound_migration_run_handler(
        attempt_handler,
        worker_identity=worker_identity,
        attempt_lease_seconds=attempt_lease_seconds,
        heartbeat_interval_s=heartbeat_interval_s,
    )
