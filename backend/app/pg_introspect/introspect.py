from __future__ import annotations

import datetime as dt
import ssl
from urllib.parse import parse_qsl, urlparse

import asyncpg

from app.pg_introspect import queries
from app.pg_introspect.column_examples import add_column_examples
from app.pg_introspect.dsn_guard import validate_postgres_dsn_target
from app.pg_introspect.forward_ddl import ForwardDdlBatch
from app.sanitize import sanitize_for_storage


class _ServerHostnameSSLContext(ssl.SSLContext):
    """SSL context that keeps certificate verification tied to the DSN host."""

    _server_hostname: str

    def __new__(cls, server_hostname: str) -> "_ServerHostnameSSLContext":
        context = super().__new__(cls, ssl.PROTOCOL_TLS_CLIENT)
        context._server_hostname = server_hostname
        return context

    def __init__(self, server_hostname: str) -> None:
        return None

    def wrap_bio(
        self,
        incoming: ssl.MemoryBIO,
        outgoing: ssl.MemoryBIO,
        server_side: bool = False,
        server_hostname: str | bytes | None = None,
        session: ssl.SSLSession | None = None,
    ) -> ssl.SSLObject:
        return super().wrap_bio(
            incoming,
            outgoing,
            server_side=server_side,
            server_hostname=self._server_hostname,
            session=session,
        )


def _requires_verified_tls_hostname(dsn: str) -> bool:
    query = dict(parse_qsl(urlparse(dsn).query, keep_blank_values=True))
    return query.get("sslmode", "").lower() == "verify-full"


def _verified_tls_context(dsn: str, server_hostname: str) -> ssl.SSLContext:
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
        version = await conn.fetchval("SHOW server_version")
        schema_name = schema_filter
        include_system = False

        schemas = await conn.fetch(queries.SCHEMAS_SQL, schema_name, include_system)
        relations = await conn.fetch(queries.RELATIONS_SQL, schema_name, include_system)
        columns = await conn.fetch(queries.COLUMNS_SQL, schema_name, include_system)
        constraints = await conn.fetch(
            queries.CONSTRAINTS_SQL, schema_name, include_system
        )
        indexes = await conn.fetch(queries.INDEXES_SQL, schema_name, include_system)
        pk_columns = await conn.fetch(
            queries.PK_COLUMNS_SQL, schema_name, include_system
        )
        fk_edges = await conn.fetch(queries.FK_EDGES_SQL, schema_name, include_system)
        citus_distributed_tables = []
        has_citus = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_extension WHERE extname = 'citus')"
        )
        if has_citus:
            try:
                citus_distributed_tables = await conn.fetch(
                    queries.CITUS_DISTRIBUTED_TABLES_SQL,
                    schema_name,
                    include_system,
                )
            except asyncpg.UndefinedTableError:
                citus_distributed_tables = []

        snapshot = {
            "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "server_version": str(version),
            "schema_filter": schema_filter,
            "schemas": [dict(r) for r in schemas],
            "relations": [dict(r) for r in relations],
            "columns": add_column_examples([dict(r) for r in columns]),
            "constraints": [dict(r) for r in constraints],
            "indexes": [dict(r) for r in indexes],
            "pk_columns": [dict(r) for r in pk_columns],
            "fk_edges": [dict(r) for r in fk_edges],
            "citus_distributed_tables": [dict(r) for r in citus_distributed_tables],
        }

        return sanitize_for_storage(snapshot)  # type: ignore[return-value]
    finally:
        await conn.close()
