"""Real-PostgreSQL migration-run/outbox and live-read integration acceptance."""

from __future__ import annotations

import datetime as dt
import os
import uuid
from urllib.parse import urlparse

import asyncpg
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.forward.isolated_dry_run import execute_isolated_dry_run
from app.forward.migration_plan import compile_migration_plan
from app.forward.live_preflight import (
    LivePreflightContractError,
    execute_bound_live_preflight,
    execute_live_preflight,
)
from app.forward.migration_run import (
    claim_one_migration_dispatch,
    complete_isolated_dry_run,
    complete_live_preflight,
    create_migration_run,
    mark_migration_dispatch_published,
    transition_migration_run,
)
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
from app.pg_introspect import queries
from app.pg_introspect.snapshot_contract import (
    CURRENT_POSTGRES_SNAPSHOT_CONTRACT_VERSION,
)
from app.forward.schema_model import schema_model_digest
from app.forward.snapshot_adapter import snapshot_to_schema_model

_POSTGRES_URL = os.getenv("POSTGRES_INTEGRATION_URL")
_POSTGRES_SANDBOX_URL = os.getenv("POSTGRES_SANDBOX_INTEGRATION_URL")
_POSTGRES_TARGET_URL = os.getenv("POSTGRES_TARGET_INTEGRATION_URL")
_POSTGRES_PREFLIGHT_URL = os.getenv("POSTGRES_PREFLIGHT_INTEGRATION_URL")
_EXPECTED_MAJOR = os.getenv("EXPECTED_POSTGRES_MAJOR")
pytestmark = pytest.mark.skipif(
    not _POSTGRES_URL
    or not _POSTGRES_SANDBOX_URL
    or not _POSTGRES_TARGET_URL
    or not _POSTGRES_PREFLIGHT_URL
    or not _EXPECTED_MAJOR,
    reason=(
        "metadata, sandbox, target-admin, preflight, and expected-major "
        "configuration are required for real PostgreSQL acceptance"
    ),
)


def _asyncpg_url() -> str:
    assert _POSTGRES_URL is not None
    return _POSTGRES_URL.replace("postgresql+asyncpg://", "postgresql://", 1)


def _sandbox_asyncpg_url() -> str:
    assert _POSTGRES_SANDBOX_URL is not None
    return _POSTGRES_SANDBOX_URL.replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


def _target_asyncpg_url() -> str:
    assert _POSTGRES_TARGET_URL is not None
    return _POSTGRES_TARGET_URL.replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


def _preflight_asyncpg_url() -> str:
    assert _POSTGRES_PREFLIGHT_URL is not None
    return _POSTGRES_PREFLIGHT_URL.replace(
        "postgresql+asyncpg://", "postgresql://", 1
    )


def _preflight_plan(*preconditions: dict[str, object]) -> dict[str, object]:
    return {
        "can_dry_run": True,
        "blockers": [],
        "statements": [{"preconditions": list(preconditions)}],
    }


async def _capture_filtered_snapshot(
    connection: asyncpg.Connection[asyncpg.Record], schema_name: str
) -> dict[str, object]:
    """Capture the strict capability rows from the owned sandbox connection."""

    include_system = False
    return {
        "snapshot_contract_version": CURRENT_POSTGRES_SNAPSHOT_CONTRACT_VERSION,
        "server_version": str(await connection.fetchval("SHOW server_version")),
        "schemas": [
            dict(row)
            for row in await connection.fetch(
                queries.SCHEMAS_SQL, schema_name, include_system
            )
        ],
        "relations": [
            dict(row)
            for row in await connection.fetch(
                queries.RELATIONS_SQL, schema_name, include_system
            )
        ],
        "columns": [
            dict(row)
            for row in await connection.fetch(
                queries.COLUMNS_SQL, schema_name, include_system
            )
        ],
        "constraints": [
            dict(row)
            for row in await connection.fetch(
                queries.CONSTRAINTS_SQL, schema_name, include_system
            )
        ],
        "indexes": [
            dict(row)
            for row in await connection.fetch(
                queries.INDEXES_SQL, schema_name, include_system
            )
        ],
        "pk_columns": [
            dict(row)
            for row in await connection.fetch(
                queries.PK_COLUMNS_SQL, schema_name, include_system
            )
        ],
        "fk_edges": [
            dict(row)
            for row in await connection.fetch(
                queries.FK_EDGES_SQL, schema_name, include_system
            )
        ],
    }


@pytest.mark.asyncio
async def test_real_postgres_executes_exact_isolated_plan_and_converges() -> None:
    """Prove exact signed-plan execution and re-introspection on PostgreSQL."""

    assert _EXPECTED_MAJOR is not None
    assert _POSTGRES_URL is not None
    assert _POSTGRES_SANDBOX_URL is not None
    assert urlparse(_POSTGRES_URL).path != urlparse(_POSTGRES_SANDBOX_URL).path
    major = int(_EXPECTED_MAJOR)
    schema_name = f"Dry Run {uuid.uuid4().hex}"
    table_name = '주문 "항목"'
    base = {"format_version": 1, "postgresql_major": major, "schemas": []}
    target = {
        "format_version": 1,
        "postgresql_major": major,
        "schemas": [
            {
                "schema_name": schema_name,
                "tables": [
                    {
                        "table_name": table_name,
                        "columns": [
                            {
                                "column_name": "Item ID",
                                "data_type": "bigint",
                                "nullable": True,
                                "ordinal_position": 1,
                            }
                        ],
                    }
                ],
            }
        ],
    }
    plan = compile_migration_plan(base, target)
    connection = await asyncpg.connect(_sandbox_asyncpg_url())

    async def capture(
        owned_connection: asyncpg.Connection[asyncpg.Record],
    ) -> dict[str, object]:
        return await _capture_filtered_snapshot(owned_connection, schema_name)

    quoted_schema = '"' + schema_name.replace('"', '""') + '"'
    try:
        evidence = await execute_isolated_dry_run(
            connection,
            plan,
            expected_plan_digest=plan["plan_digest"],
            capture_snapshot=capture,  # type: ignore[arg-type]
            lock_timeout_ms=2_000,
            statement_timeout_ms=5_000,
        )
        assert evidence == {
            "postgresql_major": major,
            "statement_count": 2,
            "base_digest": plan["base_digest"],
            "target_digest": plan["target_digest"],
            "converged": True,
        }
        assert await connection.fetchval(
            "SELECT EXISTS ("
            "SELECT 1 FROM pg_catalog.pg_class AS c "
            "JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace "
            "WHERE n.nspname = $1 AND c.relname = $2)",
            schema_name,
            table_name,
        ) is True
    finally:
        await connection.execute(f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE")
        await connection.close()


@pytest.mark.asyncio
async def test_real_postgres_executes_only_bounded_preflight_reads() -> None:
    """Prove least-privilege reads, DDL denial, and fixed failures."""

    assert _POSTGRES_URL is not None
    assert _POSTGRES_SANDBOX_URL is not None
    assert _POSTGRES_TARGET_URL is not None
    assert _POSTGRES_PREFLIGHT_URL is not None
    database_paths = {
        urlparse(_POSTGRES_URL).path,
        urlparse(_POSTGRES_SANDBOX_URL).path,
        urlparse(_POSTGRES_TARGET_URL).path,
    }
    assert len(database_paths) == 3
    admin_connection = await asyncpg.connect(_target_asyncpg_url())
    schema_name = f"Preflight {uuid.uuid4().hex}"
    table_name = '주문 "항목"'
    quoted_schema = '"' + schema_name.replace('"', '""') + '"'
    quoted_table = '"' + table_name.replace('"', '""') + '"'
    qualified = f"{quoted_schema}.{quoted_table}"
    try:
        await admin_connection.execute(f"CREATE SCHEMA {quoted_schema}")
        await admin_connection.execute(
            f'CREATE TABLE {qualified} ("amount value" text)'
        )
        await admin_connection.execute(
            f"INSERT INTO {qualified} VALUES ('12'), ('not-an-integer'), (NULL)"
        )
        await admin_connection.execute(
            f"GRANT USAGE ON SCHEMA {quoted_schema} TO cwl_erd_preflight"
        )
        await admin_connection.execute(
            f"GRANT SELECT ON {qualified} TO cwl_erd_preflight"
        )
        planned_snapshot = await _capture_filtered_snapshot(
            admin_connection, schema_name
        )
        plan = _preflight_plan(
            {
                "kind": "table_is_empty",
                "schema_name": schema_name,
                "table_name": table_name,
            },
            {
                "kind": "no_null_values",
                "schema_name": schema_name,
                "table_name": table_name,
                "column_name": "amount value",
            },
        )
        plan["base_digest"] = schema_model_digest(
            snapshot_to_schema_model(planned_snapshot)
        )
        connection = await asyncpg.connect(_preflight_asyncpg_url())
        try:
            privileges = await connection.fetchrow(
                "SELECT "
                "pg_catalog.has_database_privilege("
                "current_user, current_database(), 'CREATE') AS can_create, "
                "pg_catalog.has_database_privilege("
                "current_user, current_database(), 'TEMP') AS can_temp"
            )
            assert dict(privileges) == {
                "can_create": False,
                "can_temp": False,
            }
            role_attributes = await connection.fetchrow(
                "SELECT rolsuper, rolcreaterole, rolcreatedb, rolreplication, "
                "rolbypassrls FROM pg_catalog.pg_roles WHERE rolname = current_user"
            )
            assert dict(role_attributes) == {
                "rolsuper": False,
                "rolcreaterole": False,
                "rolcreatedb": False,
                "rolreplication": False,
                "rolbypassrls": False,
            }
            with pytest.raises(
                (
                    asyncpg.InsufficientPrivilegeError,
                    asyncpg.ReadOnlySQLTransactionError,
                )
            ):
                await connection.execute(
                    f'CREATE TABLE {quoted_schema}."must not exist" (id integer)'
                )

            async def capture(
                owned_connection: asyncpg.Connection[asyncpg.Record],
            ) -> dict[str, object]:
                return await _capture_filtered_snapshot(
                    owned_connection, schema_name
                )

            evidence = await execute_bound_live_preflight(
                connection,
                plan,
                capture_snapshot=capture,  # type: ignore[arg-type]
                statement_timeout_ms=2000,
            )

            assert evidence == {
                "preconditions_passed": False,
                "checks": [
                    {
                        "statement_index": 0,
                        "precondition_index": 0,
                        "kind": "table_is_empty",
                        "passed": False,
                    },
                    {
                        "statement_index": 0,
                        "precondition_index": 1,
                        "kind": "no_null_values",
                        "passed": False,
                    },
                ],
                "observed_base_digest": plan["base_digest"],
                "matches_plan_base": True,
            }

            with pytest.raises(LivePreflightContractError) as captured:
                await execute_live_preflight(
                    connection,
                    _preflight_plan(
                        {
                            "kind": "castable_values",
                            "schema_name": schema_name,
                            "table_name": table_name,
                            "column_name": "amount value",
                            "target_data_type": "integer",
                        }
                    ),
                    statement_timeout_ms=2000,
                )
            assert str(captured.value) == "live preflight query failed"
            assert captured.value.__cause__ is None

            await admin_connection.execute(f"DELETE FROM {qualified}")
            empty_evidence = await execute_live_preflight(
                connection,
                _preflight_plan(
                    {
                        "kind": "table_is_empty",
                        "schema_name": schema_name,
                        "table_name": table_name,
                    }
                ),
                statement_timeout_ms=2000,
            )
            assert empty_evidence["passed"] is True
        finally:
            await connection.close()
    finally:
        await admin_connection.execute(
            f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE"
        )
        await admin_connection.close()


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
            assert _EXPECTED_MAJOR is not None
            assert server_version_num // 10_000 == int(_EXPECTED_MAJOR)
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
            claim = await claim_one_migration_dispatch(session, now=now)
            assert claim is not None
            assert claim.migration_run_uuid == first.migration_run_uuid
            assert claim.migration_run_dispatch_uuid == (
                dispatch.migration_run_dispatch_uuid
            )
            assert claim.dispatch_kind == "isolated_dry_run"
            assert claim.attempt_count == 1
            await mark_migration_dispatch_published(
                session,
                claim=claim,
                now=now + dt.timedelta(seconds=1),
            )
            await session.refresh(dispatch)
            assert dispatch.status == "published"
            assert dispatch.attempt_count == 1
            assert dispatch.published_at == now + dt.timedelta(seconds=1)
            await transition_migration_run(
                session,
                migration_run_uuid=first.migration_run_uuid,
                expected_state_version=1,
                next_state="sandbox_running",
                event_type="sandbox_started",
                evidence={"postgresql_major": int(_EXPECTED_MAJOR)},
                actor_user_uuid=None,
                now=now + dt.timedelta(seconds=2),
            )
            await session.flush()
            await complete_isolated_dry_run(
                session,
                migration_run_uuid=first.migration_run_uuid,
                expected_state_version=2,
                result={
                    "postgresql_major": int(_EXPECTED_MAJOR),
                    "statement_count": len(plan.plan_json["statements"]),
                    "base_digest": plan.base_digest,
                    "target_digest": plan.target_digest,
                    "converged": True,
                },
                actor_user_uuid=None,
                now=now + dt.timedelta(seconds=3),
            )
            await session.flush()
            await complete_live_preflight(
                session,
                migration_run_uuid=first.migration_run_uuid,
                expected_state_version=3,
                result={
                    "preconditions_passed": True,
                    "checks": [],
                    "observed_base_digest": plan.base_digest,
                    "matches_plan_base": True,
                },
                actor_user_uuid=None,
                now=now + dt.timedelta(seconds=4),
            )
            await session.flush()
            persisted_run = await session.scalar(
                select(MigrationRun).where(
                    MigrationRun.migration_run_uuid == first.migration_run_uuid
                )
            )
            assert persisted_run is not None
            assert persisted_run.state == "passed"
            assert persisted_run.state_version == 4
            assert persisted_run.observed_base_digest == plan.base_digest
            assert await session.scalar(
                select(func.count(MigrationRunEvent.migration_run_event_uuid)).where(
                    MigrationRunEvent.migration_run_uuid == first.migration_run_uuid
                )
            ) == 4

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
