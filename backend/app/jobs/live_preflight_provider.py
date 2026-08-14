"""Guarded stored-PostgreSQL provider for bounded live preflight only."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from app.jobs.migration_dry_run_worker import (
    LivePreflightExecution,
    LivePreflightRequest,
    MigrationDryRunWorkerError,
    load_guarded_live_preflight_target,
)
from app.jobs.migration_dry_run_worker_contract import (
    LivePreflightFactory,
    SessionFactory,
)
from app.pg_introspect.introspect import (
    capture_postgres_snapshot,
    connect_guarded_postgres,
)
from app.security import decrypt_text

__all__ = ["make_stored_postgres_live_preflight_factory"]

_CONNECT_TIMEOUT_SECONDS = 10.0


def _provider_error() -> MigrationDryRunWorkerError:
    """Return the one non-reflecting provider acquisition error."""

    return MigrationDryRunWorkerError(
        "migration live-preflight provider failed"
    )


def make_stored_postgres_live_preflight_factory(
    session_factory: SessionFactory,
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
                dsn, timeout=_CONNECT_TIMEOUT_SECONDS
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
