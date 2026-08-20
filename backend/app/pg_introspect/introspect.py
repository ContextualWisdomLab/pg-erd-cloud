"""Guarded PostgreSQL connectivity and snapshot introspection helpers."""

from __future__ import annotations

import ssl
from urllib.parse import parse_qsl, urlparse

import asyncpg

from app.pg_introspect.dsn_guard import validate_postgres_dsn_target
from app.pg_introspect.forward_ddl import ForwardDdlBatch
from app.pg_introspect.snapshot_collect import collect_postgres_snapshot


class _ServerHostnameSSLContext(ssl.SSLContext):
    """SSL context that keeps certificate verification tied to the DSN host."""

    _server_hostname: str

    def __new__(cls, server_hostname: str) -> "_ServerHostnameSSLContext":
        """Create a client TLS context that retains the verified DSN hostname."""
        context = super().__new__(cls, ssl.PROTOCOL_TLS_CLIENT)
        context._server_hostname = server_hostname
        return context

    def __init__(self, server_hostname: str) -> None:
        """Keep the SSL context initialized by ``__new__`` without resetting it."""
        return None

    def wrap_bio(
        self,
        incoming: ssl.MemoryBIO,
        outgoing: ssl.MemoryBIO,
        server_side: bool = False,
        server_hostname: str | bytes | None = None,
        session: ssl.SSLSession | None = None,
    ) -> ssl.SSLObject:
        """Wrap a TLS BIO while forcing certificate verification to the DSN host."""
        return super().wrap_bio(
            incoming,
            outgoing,
            server_side=server_side,
            server_hostname=self._server_hostname,
            session=session,
        )


def _requires_verified_tls_hostname(dsn: str) -> bool:
    """Return whether the DSN requests PostgreSQL ``verify-full`` TLS mode."""
    query = dict(parse_qsl(urlparse(dsn).query, keep_blank_values=True))
    return query.get("sslmode", "").lower() == "verify-full"


def _verified_tls_context(dsn: str, server_hostname: str) -> ssl.SSLContext:
    """Build a TLS context from DSN certificate options with hostname binding."""
    query = dict(parse_qsl(urlparse(dsn).query, keep_blank_values=True))
    context = _ServerHostnameSSLContext(server_hostname)
    if query.get("sslrootcert"):
        context.load_verify_locations(cafile=query["sslrootcert"])
    else:
        context.load_default_certs()
    if query.get("sslcert") and query.get("sslkey"):
        context.load_cert_chain(query["sslcert"], query["sslkey"])
    return context


async def _connect_guarded_postgres(
    dsn: str, *, timeout: float
) -> asyncpg.Connection:
    """Validate a DSN and connect only to its resolved, permitted host targets."""
    target = await validate_postgres_dsn_target(dsn)
    connect_host: str | list[str] = (
        target.hosts[0] if len(target.hosts) == 1 else list(target.hosts)
    )
    ssl_context = (
        _verified_tls_context(dsn, target.hostname)
        if _requires_verified_tls_hostname(dsn)
        else None
    )
    if target.port is not None:
        if ssl_context is not None:
            return await asyncpg.connect(
                dsn,
                host=connect_host,
                port=target.port,
                timeout=timeout,
                ssl=ssl_context,
            )
        return await asyncpg.connect(
            dsn, host=connect_host, port=target.port, timeout=timeout
        )
    if ssl_context is not None:
        return await asyncpg.connect(
            dsn, host=connect_host, timeout=timeout, ssl=ssl_context
        )
    return await asyncpg.connect(dsn, host=connect_host, timeout=timeout)


async def probe_postgres(dsn: str) -> str:
    """SSRF-guarded connectivity check: connect and return the server version."""

    conn = await _connect_guarded_postgres(dsn, timeout=10)
    try:
        await conn.fetchval("SELECT 1")
        return str(await conn.fetchval("SHOW server_version"))
    finally:
        await conn.close()


async def apply_postgres_ddl(
    dsn: str, ddl: ForwardDdlBatch, dry_run: bool = True
) -> None:
    """Execute validated forward-apply DDL inside one PostgreSQL transaction.

    The caller supplies a ``ForwardDdlBatch`` produced by the forward DDL
    validator; arbitrary SQL text is not accepted here. The connection path is
    SSRF-guarded exactly like introspection, including pinned IP and verified
    TLS hostname handling.
    """

    conn = await _connect_guarded_postgres(dsn, timeout=15)
    try:
        tx = conn.transaction()
        await tx.start()
        try:
            await conn.execute(ddl.sql)
        except BaseException:
            await tx.rollback()
            raise
        if dry_run:
            await tx.rollback()
        else:
            await tx.commit()
    finally:
        await conn.close()


async def introspect_postgres(dsn: str, schema_filter: str | None) -> dict:
    """Introspect a PostgreSQL database and return a snapshot JSON."""

    # Note: avoid logging DSN.
    conn = await _connect_guarded_postgres(dsn, timeout=10)
    try:
        return await collect_postgres_snapshot(conn, schema_filter)
    finally:
        await conn.close()
