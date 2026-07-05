from __future__ import annotations

import datetime as dt

import asyncpg

from app.pg_introspect import queries
from app.pg_introspect.column_examples import add_column_examples
from app.pg_introspect.dsn_guard import validate_postgres_dsn_target
from app.sanitize import sanitize_for_storage


async def probe_postgres(dsn: str) -> str:
    """SSRF-guarded connectivity check: connect and return the server version.

    Reuses ``validate_postgres_dsn_target`` and connects to the pinned IP, so
    the same anti-SSRF guarantees as full introspection apply.
    """
    target = await validate_postgres_dsn_target(dsn)
    connect_host: str | list[str] = (
        target.hosts[0] if len(target.hosts) == 1 else list(target.hosts)
    )
    if target.port is not None:
        conn = await asyncpg.connect(
            dsn, host=connect_host, port=target.port, timeout=10
        )
    else:
        conn = await asyncpg.connect(dsn, host=connect_host, timeout=10)
    try:
        await conn.fetchval("SELECT 1")
        return str(await conn.fetchval("SHOW server_version"))
    finally:
        await conn.close()


async def apply_postgres_sql(dsn: str, sql: str, dry_run: bool = True) -> None:
    """Execute DDL/SQL against a target Postgres DB inside one transaction.

    Forward engineering: materialize a designed schema / apply a migration.
    SSRF-guarded exactly like introspection (``validate_postgres_dsn_target`` +
    pinned IP). The whole batch runs in a single transaction:

    * ``dry_run=True`` (default) rolls back, so nothing persists -- a pre-flight
      validation that the SQL executes cleanly against the real database.
    * ``dry_run=False`` commits.

    PostgreSQL DDL is transactional, so a mid-batch failure rolls everything
    back. Statements that cannot run inside a transaction (e.g.
    ``CREATE INDEX CONCURRENTLY``) will raise here -- that is expected.
    """
    target = await validate_postgres_dsn_target(dsn)
    connect_host: str | list[str] = (
        target.hosts[0] if len(target.hosts) == 1 else list(target.hosts)
    )
    if target.port is not None:
        conn = await asyncpg.connect(
            dsn, host=connect_host, port=target.port, timeout=15
        )
    else:
        conn = await asyncpg.connect(dsn, host=connect_host, timeout=15)
    try:
        tx = conn.transaction()
        await tx.start()
        try:
            await conn.execute(sql)
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
    target = await validate_postgres_dsn_target(dsn)
    connect_host: str | list[str] = (
        target.hosts[0] if len(target.hosts) == 1 else list(target.hosts)
    )
    if target.port is not None:
        conn = await asyncpg.connect(
            dsn, host=connect_host, port=target.port, timeout=10
        )
    else:
        conn = await asyncpg.connect(dsn, host=connect_host, timeout=10)
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
