from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DbConnection,
    JobQueue,
    SchemaSnapshot,
    SchemaSnapshotData,
)
from app.pg_introspect.dsn_guard import validate_postgres_dsn_target
from app.pg_introspect.introspect import introspect_postgres
from app.security import decrypt_text


async def handle_snapshot_job(
    session_factory: Callable[[], AsyncSession],
    job: JobQueue,
) -> None:
    """Run a schema snapshot job and persist the resulting JSON."""
    payload = job.payload_json
    snapshot_id = uuid.UUID(payload["schema_snapshot_uuid"])
    async with session_factory() as session:
        async with session.begin():
            snapshot = await session.get(SchemaSnapshot, snapshot_id)
            if snapshot is None:
                raise RuntimeError("snapshot not found")
            snapshot.status = "running"
            snapshot.started_at = dt.datetime.now(dt.timezone.utc)

            conn = await session.get(DbConnection, snapshot.db_connection_uuid)
            if conn is None:
                raise RuntimeError("db connection not found")

            dsn = decrypt_text(conn.dsn_ciphertext, conn.dsn_nonce)
            validate_postgres_dsn_target(dsn)
            schema_filter = snapshot.schema_filter

    # Long-running IO: do it outside a DB transaction.
    try:
        data = await introspect_postgres(dsn, schema_filter)
    except Exception as e:  # noqa: BLE001
        async with session_factory() as session:
            async with session.begin():
                snapshot = await session.get(SchemaSnapshot, snapshot_id)
                if snapshot is None:
                    raise
                snapshot.status = "failed"
                snapshot.error_message = str(e)
                snapshot.finished_at = dt.datetime.now(dt.timezone.utc)
        raise

    async with session_factory() as session:
        async with session.begin():
            snapshot = await session.get(SchemaSnapshot, snapshot_id)
            if snapshot is None:
                raise RuntimeError("snapshot not found")

            snapshot.status = "succeeded"
            snapshot.finished_at = dt.datetime.now(dt.timezone.utc)
            snapshot.error_message = None

            existing = await session.get(SchemaSnapshotData, snapshot_id)
            if existing is None:
                session.add(
                    SchemaSnapshotData(
                        schema_snapshot_uuid=snapshot_id,
                        snapshot_json=data,
                        created_at=dt.datetime.now(dt.timezone.utc),
                    )
                )
            else:
                existing.snapshot_json = data
