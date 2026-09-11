from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import delete

from app.api.annotations import list_annotations, upsert_annotation
from app.auth import CurrentUser
from app.db import SessionLocal
from app.models import ProjectSpace, TableAnnotation, UserAccount
from app.schemas import TableAnnotationUpsertIn


pytestmark = pytest.mark.skipif(
    os.environ.get("PG_ERD_RUN_POSTGRES_INTEGRATION") != "1",
    reason="requires the PostgreSQL-backed CI integration lane",
)


@pytest.mark.asyncio
async def test_postgresql_round_trip_preserves_source_identifier() -> None:
    """Persist and read source identity through the production annotation path."""
    user_account_uuid = uuid.uuid4()
    project_space_uuid = uuid.uuid4()
    user = CurrentUser(
        user_account_uuid=user_account_uuid,
        subject="postgres-roundtrip",
        display_name="PostgreSQL round-trip",
    )
    body = TableAnnotationUpsertIn(
        schema_name="audit\x01trail",
        relation_name="line\x7fitem",
        body="round-trip acceptance",
    )

    try:
        async with SessionLocal() as setup_session:
            setup_session.add(
                UserAccount(
                    user_account_uuid=user_account_uuid,
                    oidc_subject=f"postgres-roundtrip-{user_account_uuid}",
                    display_name="PostgreSQL round-trip",
                )
            )
            await setup_session.flush()
            setup_session.add(
                ProjectSpace(
                    project_space_uuid=project_space_uuid,
                    project_name="PostgreSQL identifier acceptance",
                    created_by_user_uuid=user_account_uuid,
                )
            )
            await setup_session.commit()

        async with SessionLocal() as write_session:
            with patch(
                "app.api.annotations.require_project_member",
                new_callable=AsyncMock,
            ):
                written = await upsert_annotation(
                    project_space_uuid=project_space_uuid,
                    body=body,
                    user=user,
                    session=write_session,
                )

        assert written.schema_name == body.schema_name
        assert written.relation_name == body.relation_name

        async with SessionLocal() as read_session:
            with patch(
                "app.api.annotations.require_project_member",
                new_callable=AsyncMock,
            ):
                listed = await list_annotations(
                    project_space_uuid=project_space_uuid,
                    user=user,
                    session=read_session,
                )

        assert len(listed) == 1
        assert listed[0].schema_name == body.schema_name
        assert listed[0].relation_name == body.relation_name
    finally:
        async with SessionLocal() as cleanup_session:
            await cleanup_session.execute(
                delete(TableAnnotation).where(
                    TableAnnotation.project_space_uuid == project_space_uuid
                )
            )
            await cleanup_session.execute(
                delete(ProjectSpace).where(
                    ProjectSpace.project_space_uuid == project_space_uuid
                )
            )
            await cleanup_session.execute(
                delete(UserAccount).where(
                    UserAccount.user_account_uuid == user_account_uuid
                )
            )
            await cleanup_session.commit()
