"""Real-PostgreSQL migration-run/outbox integration acceptance."""

from __future__ import annotations

import datetime as dt
import os
import uuid

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.forward.migration_plan import compile_migration_plan
from app.forward.migration_run import create_migration_run
from app.models import (
    DbConnection,
    MigrationPlan,
    MigrationRun,
    MigrationRunDispatch,
    MigrationRunEvent,
    ProjectSpace,
    SchemaModel,
    SchemaModelRevision,
    SchemaSnapshot,
    UserAccount,
)

_POSTGRES_URL = os.getenv("POSTGRES_INTEGRATION_URL")
pytestmark = pytest.mark.skipif(
    not _POSTGRES_URL,
    reason="POSTGRES_INTEGRATION_URL is required for real PostgreSQL acceptance",
)


@pytest.mark.asyncio
async def test_real_postgres_creates_one_atomic_identifier_only_dispatch() -> None:
    """Prove migration, idempotency, outbox shape, and rollback on PostgreSQL."""

    assert _POSTGRES_URL is not None
    engine = create_async_engine(_POSTGRES_URL)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    now = dt.datetime.now(dt.timezone.utc)
    user_uuid = uuid.uuid4()
    project_uuid = uuid.uuid4()
    connection_uuid = uuid.uuid4()
    snapshot_uuid = uuid.uuid4()
    model_uuid = uuid.uuid4()
    revision_uuid = uuid.uuid4()
    plan_uuid = uuid.uuid4()
    plan_json = compile_migration_plan(
        {"format_version": 1, "postgresql_major": 18, "schemas": []},
        {"format_version": 1, "postgresql_major": 18, "schemas": []},
    )

    try:
        async with sessions() as session:
            server_version_num = int(
                await session.scalar(
                    text("SELECT current_setting('server_version_num')")
                )
            )
            assert server_version_num // 10_000 == int(
                os.environ["EXPECTED_POSTGRES_MAJOR"]
            )
            session.add(
                UserAccount(
                    user_account_uuid=user_uuid,
                    oidc_subject=f"integration:{user_uuid}",
                    display_name="PostgreSQL integration",
                    created_at=now,
                )
            )
            await session.flush()
            session.add(
                ProjectSpace(
                    project_space_uuid=project_uuid,
                    project_name="migration run integration",
                    created_by_user_uuid=user_uuid,
                    created_at=now,
                )
            )
            await session.flush()
            session.add(
                DbConnection(
                    db_connection_uuid=connection_uuid,
                    project_space_uuid=project_uuid,
                    conn_name="integration target",
                    dsn_ciphertext=b"not-used",
                    dsn_nonce=b"not-used",
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.flush()
            session.add_all(
                [
                    SchemaSnapshot(
                        schema_snapshot_uuid=snapshot_uuid,
                        project_space_uuid=project_uuid,
                        db_connection_uuid=connection_uuid,
                        status="succeeded",
                        schema_filter=None,
                        started_at=now,
                        finished_at=now,
                        error_message=None,
                        created_at=now,
                    ),
                    SchemaModel(
                        schema_model_uuid=model_uuid,
                        project_space_uuid=project_uuid,
                        model_name="integration_model",
                        current_revision_number=1,
                        created_by_user_uuid=user_uuid,
                        created_at=now,
                        updated_at=now,
                    ),
                ]
            )
            await session.flush()
            session.add(
                SchemaModelRevision(
                    schema_model_revision_uuid=revision_uuid,
                    schema_model_uuid=model_uuid,
                    revision_number=1,
                    revision_digest=plan_json["target_digest"],
                    model_json={
                        "format_version": 1,
                        "postgresql_major": 18,
                        "schemas": [],
                    },
                    base_schema_snapshot_uuid=snapshot_uuid,
                    created_by_user_uuid=user_uuid,
                    created_at=now,
                )
            )
            await session.flush()
            plan = MigrationPlan(
                migration_plan_uuid=plan_uuid,
                project_space_uuid=project_uuid,
                schema_model_revision_uuid=revision_uuid,
                db_connection_uuid=connection_uuid,
                base_schema_snapshot_uuid=snapshot_uuid,
                compiler_version=plan_json["compiler_version"],
                base_digest=plan_json["base_digest"],
                target_digest=plan_json["target_digest"],
                statement_digest=plan_json["plan_digest"],
                plan_json=plan_json,
                created_by_user_uuid=user_uuid,
                expires_at=now + dt.timedelta(hours=1),
                created_at=now,
            )
            session.add(plan)
            await session.flush()

            first = await create_migration_run(
                session,
                plan=plan,
                run_kind="dry_run",
                idempotency_key="real-postgres-retry-key",
                requested_by_user_uuid=user_uuid,
                evidence={"request_source": "postgresql_matrix"},
                now=now,
            )
            await session.flush()
            reused = await create_migration_run(
                session,
                plan=plan,
                run_kind="dry_run",
                idempotency_key="real-postgres-retry-key",
                requested_by_user_uuid=user_uuid,
                evidence={"request_source": "postgresql_matrix"},
                now=now,
            )
            await session.flush()

            assert reused.migration_run_uuid == first.migration_run_uuid
            assert reused.reused is True
            assert await session.scalar(
                select(func.count(MigrationRun.migration_run_uuid)).where(
                    MigrationRun.migration_run_uuid == first.migration_run_uuid
                )
            ) == 1
            assert await session.scalar(
                select(func.count(MigrationRunEvent.migration_run_event_uuid)).where(
                    MigrationRunEvent.migration_run_uuid == first.migration_run_uuid
                )
            ) == 1
            dispatch = await session.scalar(
                select(MigrationRunDispatch).where(
                    MigrationRunDispatch.migration_run_uuid
                    == first.migration_run_uuid
                )
            )
            assert dispatch is not None
            assert dispatch.dispatch_kind == "isolated_dry_run"
            assert dispatch.status == "pending"
            assert dispatch.attempt_count == 0
            assert {
                column.name for column in MigrationRunDispatch.__table__.columns
            }.isdisjoint({"payload_json", "dsn", "sql", "plan_json"})

            await session.rollback()

        async with sessions() as session:
            assert await session.scalar(
                select(func.count(MigrationRun.migration_run_uuid)).where(
                    MigrationRun.migration_run_uuid == first.migration_run_uuid
                )
            ) == 0
            assert await session.scalar(
                select(func.count(MigrationRunDispatch.migration_run_uuid)).where(
                    MigrationRunDispatch.migration_run_uuid
                    == first.migration_run_uuid
                )
            ) == 0
    finally:
        await engine.dispose()
