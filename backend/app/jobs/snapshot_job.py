from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Callable
from urllib.parse import quote, quote_plus, unquote, unquote_plus, urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    DbConnection,
    JobQueue,
    SchemaSnapshot,
    SchemaSnapshotData,
)
from app.db_introspect import introspect_database
from app.security import decrypt_text

_SECRET_QUERY_KEYS = frozenset(
    {
        "password",
        "pass",
        "pwd",
        "token",
        "secret",
        "private_key",
    }
)


def _password_candidates_from_dsn(dsn: str) -> set[str]:
    candidates: set[str] = set()
    parsed = urlsplit(dsn)

    if parsed.password:
        candidates.add(parsed.password)
        candidates.add(quote(parsed.password, safe=""))

    if "@" in parsed.netloc:
        userinfo = parsed.netloc.rsplit("@", 1)[0]
        if ":" in userinfo:
            raw_password = userinfo.split(":", 1)[1]
            candidates.add(raw_password)
            candidates.add(unquote(raw_password))

    for part in parsed.query.split("&"):
        key, sep, raw_value = part.partition("=")
        if not sep:
            continue
        if unquote_plus(key).lower() not in _SECRET_QUERY_KEYS:
            continue
        decoded_value = unquote_plus(raw_value)
        candidates.add(raw_value)
        candidates.add(decoded_value)
        candidates.add(quote(decoded_value, safe=""))
        candidates.add(quote_plus(decoded_value, safe=""))

    return {candidate for candidate in candidates if candidate}


def _redact_snapshot_error_message(error_message: str, dsn: str) -> str:
    redacted = error_message
    for secret in sorted(_password_candidates_from_dsn(dsn), key=len, reverse=True):
        redacted = redacted.replace(secret, "***")
    return redacted


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
            schema_filter = snapshot.schema_filter

    # Long-running IO: do it outside a DB transaction.
    try:
        data = await introspect_database(dsn, schema_filter)
    except Exception as e:  # noqa: BLE001
        error_message = _redact_snapshot_error_message(str(e), dsn)
        async with session_factory() as session:
            async with session.begin():
                snapshot = await session.get(SchemaSnapshot, snapshot_id)
                if snapshot is None:
                    raise
                snapshot.status = "failed"
                snapshot.error_message = error_message
                snapshot.finished_at = dt.datetime.now(dt.timezone.utc)
        raise RuntimeError(error_message) from None

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
