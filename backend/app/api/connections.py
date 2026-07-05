from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.db import get_read_session, get_session
from app.db_introspect import apply_database_sql, probe_database
from app.models import DbConnection
from app.permissions import require_project_member
from app.schemas import (
    ApplySqlIn,
    ApplySqlOut,
    ConnectionCreateIn,
    ConnectionOut,
    ConnectionTestOut,
)
from app.security import decrypt_text, encrypt_text
from app.sanitize import sanitize_for_storage

router = APIRouter(prefix="/api/connections", tags=["connections"])


@router.get("/by-project/{project_space_uuid}", response_model=list[ConnectionOut])
async def list_connections(
    project_space_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> list[ConnectionOut]:
    """List DB connections for a project."""
    await require_project_member(session, project_space_uuid, user.user_account_uuid)
    rows = await session.execute(
        select(DbConnection)
        .where(DbConnection.project_space_uuid == project_space_uuid)
        .order_by(DbConnection.created_at.desc())
    )
    cons = rows.scalars().all()
    return [
        ConnectionOut(db_connection_uuid=c.db_connection_uuid, conn_name=c.conn_name)
        for c in cons
    ]


@router.post("/by-project/{project_space_uuid}", response_model=ConnectionOut)
async def create_connection(
    project_space_uuid: uuid.UUID,
    body: ConnectionCreateIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ConnectionOut:
    """Create a DB connection for a project (encrypt DSN at rest)."""
    await require_project_member(
        session, project_space_uuid, user.user_account_uuid, minimum_role="editor"
    )
    encrypted = encrypt_text(str(sanitize_for_storage(body.dsn)))
    c = DbConnection(
        db_connection_uuid=uuid.uuid4(),
        project_space_uuid=project_space_uuid,
        conn_name=str(sanitize_for_storage(body.conn_name)),
        dsn_ciphertext=encrypted.ciphertext,
        dsn_nonce=encrypted.nonce,
        created_at=dt.datetime.now(dt.timezone.utc),
        updated_at=dt.datetime.now(dt.timezone.utc),
    )
    session.add(c)
    await session.commit()
    return ConnectionOut(db_connection_uuid=c.db_connection_uuid, conn_name=c.conn_name)


@router.post("/{db_connection_uuid}/test", response_model=ConnectionTestOut)
async def test_connection(
    db_connection_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> ConnectionTestOut:
    """Probe a stored connection's DSN and report reachability.

    IDOR-safe: the connection's project is resolved first and membership is
    required, with a uniform 404 for missing/unauthorized. The DSN is decrypted
    only in memory; the live probe reuses the introspectors' SSRF guard, and any
    failure message is DSN-redacted (``ok=false`` rather than an error status,
    since an unreachable database is a normal result).
    """
    project_space_uuid = await session.scalar(
        select(DbConnection.project_space_uuid).where(
            DbConnection.db_connection_uuid == db_connection_uuid
        )
    )
    if project_space_uuid is None:
        raise HTTPException(status_code=404, detail="connection not found")
    try:
        await require_project_member(
            session, project_space_uuid, user.user_account_uuid
        )
    except HTTPException as exc:
        if exc.status_code == 403:
            raise HTTPException(status_code=404, detail="connection not found")
        raise

    conn = await session.get(DbConnection, db_connection_uuid)
    if conn is None:
        raise HTTPException(status_code=404, detail="connection not found")
    dsn = decrypt_text(conn.dsn_ciphertext, conn.dsn_nonce)
    try:
        version = await probe_database(dsn)
        return ConnectionTestOut(ok=True, server_version=version, error=None)
    except Exception as exc:  # noqa: BLE001 - message is already DSN-redacted
        return ConnectionTestOut(ok=False, server_version=None, error=str(exc))


@router.post("/{db_connection_uuid}/apply-sql", response_model=ApplySqlOut)
async def apply_sql(
    db_connection_uuid: uuid.UUID,
    body: ApplySqlIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> ApplySqlOut:
    """Forward engineering: apply DDL/SQL to a stored connection's database.

    SECURITY-SENSITIVE (writes to a live database):
    * Requires the **editor** role on the connection's project.
    * IDOR-safe: non-members get a uniform 404 (no enumeration); members
      lacking editor get 403.
    * The DSN is decrypted only in memory; the connection reuses the
      introspectors' SSRF guard (validated + pinned IP).
    * Runs the whole batch in one transaction; ``dry_run`` (default True) rolls
      back so nothing persists -- callers must opt in to persist. Failure
      messages are DSN-redacted, and an execution error is ``ok=false`` rather
      than an error status (a failed apply is a normal result).
    """
    project_space_uuid = await session.scalar(
        select(DbConnection.project_space_uuid).where(
            DbConnection.db_connection_uuid == db_connection_uuid
        )
    )
    if project_space_uuid is None:
        raise HTTPException(status_code=404, detail="connection not found")
    # Membership first (mask non-members to 404), then require editor (403).
    try:
        await require_project_member(
            session, project_space_uuid, user.user_account_uuid
        )
    except HTTPException as exc:
        if exc.status_code == 403:
            raise HTTPException(status_code=404, detail="connection not found")
        raise
    await require_project_member(
        session, project_space_uuid, user.user_account_uuid, minimum_role="editor"
    )

    conn = await session.get(DbConnection, db_connection_uuid)
    if conn is None:
        raise HTTPException(status_code=404, detail="connection not found")
    dsn = decrypt_text(conn.dsn_ciphertext, conn.dsn_nonce)
    try:
        await apply_database_sql(dsn, body.sql, dry_run=body.dry_run)
        return ApplySqlOut(ok=True, dry_run=body.dry_run, error=None)
    except Exception as exc:  # noqa: BLE001 - message is already DSN-redacted
        return ApplySqlOut(ok=False, dry_run=body.dry_run, error=str(exc))
