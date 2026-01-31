from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.db import get_session
from app.models import DbConnection
from app.permissions import require_project_member
from app.schemas import ConnectionCreateIn, ConnectionOut
from app.security import encrypt_text
from app.sanitize import sanitize_for_storage


router = APIRouter(prefix="/api/connections", tags=["connections"])


@router.get("/by-project/{project_space_uuid}", response_model=list[ConnectionOut])
async def list_connections(
    project_space_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ConnectionOut]:
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
    await require_project_member(session, project_space_uuid, user.user_account_uuid)
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
