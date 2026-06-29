"""PostgreSQL Introspection Module."""
from __future__ import annotations

import datetime as dt
import ssl

import asyncpg

from app.pg_introspect import queries
from app.pg_introspect.column_examples import add_column_examples
from app.pg_introspect.dsn_guard import validate_postgres_dsn_target
from app.sanitize import sanitize_for_storage


class SNIOverrideSSLContext(ssl.SSLContext):
    """Custom SSLContext that forcefully overrides the SNI hostname to prevent SSRF DNS-rebinding attacks."""
    def __new__(
        cls,
        target_hostname: str,
        protocol: int = ssl.PROTOCOL_TLS_CLIENT,
        *args,
        **kwargs,
    ):
        """Create a new SNIOverrideSSLContext instance with the specified target hostname."""
        obj = super().__new__(cls, protocol, *args, **kwargs)
        obj._target_hostname = target_hostname
        return obj

    def wrap_bio(
        self, incoming, outgoing, server_side=False, server_hostname=None, session=None
    ):
        """Wrap the BIO object while forcefully injecting the original server_hostname for TLS SNI validation."""
        return super().wrap_bio(
            incoming,
            outgoing,
            server_side=server_side,
            server_hostname=self._target_hostname,
            session=session,
        )


async def introspect_postgres(dsn: str, schema_filter: str | None) -> dict:
    """Introspect a PostgreSQL database and return a snapshot JSON."""

    # Note: avoid logging DSN.
    target = await validate_postgres_dsn_target(dsn)
    connect_host: str | list[str] = (
        target.hosts[0] if len(target.hosts) == 1 else list(target.hosts)
    )

    # Use a custom SSLContext to inject the original hostname for SNI since asyncpg
    # will otherwise default to the IP address when connecting to connect_host.
    ssl_context = SNIOverrideSSLContext(target.hostname)

    if target.port is not None:
        conn = await asyncpg.connect(
            dsn, host=connect_host, port=target.port, timeout=10, ssl=ssl_context
        )
    else:
        conn = await asyncpg.connect(
            dsn, host=connect_host, timeout=10, ssl=ssl_context
        )
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
