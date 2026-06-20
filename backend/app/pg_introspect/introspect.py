from __future__ import annotations

import datetime as dt

import asyncpg

from app.pg_introspect import queries
from app.pg_introspect.column_examples import add_column_examples
from app.pg_introspect.dsn_guard import validate_postgres_dsn_target
from app.sanitize import sanitize_for_storage


async def introspect_postgres(dsn: str, schema_filter: str | None) -> dict:
    """Introspect a PostgreSQL database and return a snapshot JSON."""

    # Note: avoid logging DSN.
    target = validate_postgres_dsn_target(dsn)
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

        schemas = await conn.fetch(
            queries.SCHEMAS_SQL, schema_name, include_system
        )
        relations = await conn.fetch(
            queries.RELATIONS_SQL, schema_name, include_system
        )
        columns = await conn.fetch(
            queries.COLUMNS_SQL, schema_name, include_system
        )
        constraints = await conn.fetch(
            queries.CONSTRAINTS_SQL, schema_name, include_system
        )
        indexes = await conn.fetch(
            queries.INDEXES_SQL, schema_name, include_system
        )
        pk_columns = await conn.fetch(
            queries.PK_COLUMNS_SQL, schema_name, include_system
        )
        fk_edges = await conn.fetch(
            queries.FK_EDGES_SQL, schema_name, include_system
        )

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
        }

        return sanitize_for_storage(snapshot)  # type: ignore[return-value]
    finally:
        await conn.close()
