"""Shared PostgreSQL catalog snapshot collector.

This module deliberately has no application-settings import. Network trust and
credential policy are established before callers hand it an open connection.
"""

from __future__ import annotations

import datetime as dt

import asyncpg

from app.pg_introspect import queries
from app.pg_introspect.column_examples import add_column_examples
from app.sanitize import sanitize_for_storage


async def collect_postgres_snapshot(
    conn: asyncpg.Connection, schema_filter: str | None
) -> dict:
    """Collect the canonical snapshot from an authorized PostgreSQL connection."""

    version = await conn.fetchval("SHOW server_version")
    schema_name = schema_filter
    include_system = False

    # asyncpg rejects overlapping operations on one Connection. Keep these
    # catalog reads sequential unless a future caller gives the collector a
    # pool and an explicit multi-connection consistency policy.
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
        "schemas": [dict(row) for row in schemas],
        "relations": [dict(row) for row in relations],
        "columns": add_column_examples([dict(row) for row in columns]),
        "constraints": [dict(row) for row in constraints],
        "indexes": [dict(row) for row in indexes],
        "pk_columns": [dict(row) for row in pk_columns],
        "fk_edges": [dict(row) for row in fk_edges],
        "citus_distributed_tables": [
            dict(row) for row in citus_distributed_tables
        ],
    }

    return sanitize_for_storage(snapshot)  # type: ignore[return-value]
