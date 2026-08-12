"""Real-PostgreSQL migration-run/outbox and live-read integration acceptance."""

from __future__ import annotations

import asyncio
import copy
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
    acquire_migration_run_attempt,
    claim_one_migration_dispatch,
    complete_isolated_dry_run,
    complete_live_preflight,
    create_migration_run,
    finish_migration_run_attempt,
    mark_migration_dispatch_published,
    renew_migration_run_attempt,
    transition_migration_run,
)
from app.models import (
    DbConnection,
    MigrationPlan,
    MigrationRun,
    MigrationRunAttempt,
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


def _migration_models_with_precondition(
    postgresql_major: int,
) -> tuple[dict[str, object], dict[str, object]]:
    """Return one base/target pair requiring a table-emptiness check."""

    base_model: dict[str, object] = {
        "format_version": 1,
        "postgresql_major": postgresql_major,
        "schemas": [
            {
                "schema_name": "public",
                "tables": [
                    {
                        "table_name": "accounts",
                        "comment": None,
                        "columns": [
                            {
                                "column_name": "id",
                                "data_type": "bigint",
                                "nullable": False,
                                "ordinal_position": 1,
                            }
                        ],
                        "primary_key": None,
                        "unique_constraints": [],
                        "foreign_keys": [],
                        "indexes": [],
                        "unsupported_features": [],
                    }
                ],
            }
        ],
    }
    target_model = copy.deepcopy(base_model)
    target_schemas = target_model["schemas"]
    assert isinstance(target_schemas, list)
    target_table = target_schemas[0]["tables"][0]
    target_table["columns"].append(
        {
            "column_name": "tenant_id",
            "data_type": "bigint",
            "nullable": False,
            "ordinal_position": 2,
        }
    )
    return base_model, target_model


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
    """Prove least-privilege reads, DDL denial, timeout cleanup, and fixed failures."""

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
    denied_table_name = '비공개 "항목"'
    quoted_schema = '"' + schema_name.replace('"', '""') + '"'
    quoted_table = '"' + table_name.replace('"', '""') + '"'
    quoted_denied_table = '"' + denied_table_name.replace('"', '""') + '"'
    qualified = f"{quoted_schema}.{quoted_table}"
    denied_qualified = f"{quoted_schema}.{quoted_denied_table}"
    try:
        await admin_connection.execute(f"CREATE SCHEMA {quoted_schema}")
        await admin_connection.execute(
            f'CREATE TABLE {qualified} ("amount value" text)'
        )
        await admin_connection.execute(
            f'CREATE TABLE {denied_qualified} ("private value" text)'
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

            blocking_transaction = admin_connection.transaction()
            await blocking_transaction.start()
            try:
                await admin_connection.execute(
                    f"LOCK TABLE {qualified} IN ACCESS EXCLUSIVE MODE"
                )
                with pytest.raises(LivePreflightContractError) as timed_out:
                    await execute_live_preflight(
                        connection,
                        _preflight_plan(
                            {
                                "kind": "table_is_empty",
                                "schema_name": schema_name,
                                "table_name": table_name,
                            }
                        ),
                        statement_timeout_ms=100,
                    )
                assert str(timed_out.value) == "live preflight query failed"
                assert timed_out.value.__cause__ is None
                assert connection.is_in_transaction() is False
            finally:
                await blocking_transaction.rollback()

            with pytest.raises(LivePreflightContractError) as denied:
                await execute_live_preflight(
                    connection,
                    _preflight_plan(
                        {
                            "kind": "table_is_empty",
                            "schema_name": schema_name,
                            "table_name": denied_table_name,
                        }
                    ),
                    statement_timeout_ms=2000,
                )
            assert str(denied.value) == "live preflight query failed"
            assert denied.value.__cause__ is None
            assert connection.is_in_transaction() is False

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

            backend_pid = connection.get_server_pid()
            blocking_transaction = admin_connection.transaction()
            await blocking_transaction.start()
            interrupted = None
            try:
                await admin_connection.execute(
                    f"LOCK TABLE {qualified} IN ACCESS EXCLUSIVE MODE"
                )
                interrupted = asyncio.create_task(
                    execute_live_preflight(
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
                )
                for _ in range(100):
                    if await admin_connection.fetchval(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM pg_catalog.pg_stat_activity
                            WHERE pid = $1
                              AND state = 'active'
                              AND wait_event_type = 'Lock'
                        )
                        """,
                        backend_pid,
                    ):
                        break
                    assert not interrupted.done(), (
                        "live preflight finished before entering its lock wait"
                    )
                    await asyncio.sleep(0.01)
                else:
                    pytest.fail(
                        "live preflight did not enter a lock wait before timeout"
                    )
                assert await admin_connection.fetchval(
                    "SELECT pg_catalog.pg_terminate_backend($1)", backend_pid
                ) is True
                with pytest.raises(LivePreflightContractError) as disconnected:
                    unexpected_result = await interrupted
                    pytest.fail(
                        "terminated live preflight unexpectedly returned "
                        f"{type(unexpected_result).__name__}"
                    )
                assert str(disconnected.value) == "live preflight query failed"
                assert disconnected.value.__cause__ is None
                assert connection.is_closed() is True
            finally:
                if interrupted is not None:
                    if not interrupted.done():
                        interrupted.cancel()
                    await asyncio.gather(interrupted, return_exceptions=True)
                await blocking_transaction.rollback()
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
    assert _EXPECTED_MAJOR is not None
    expected_major = int(_EXPECTED_MAJOR)
    base_model, target_model = _migration_models_with_precondition(expected_major)
    plan_json = compile_migration_plan(base_model, target_model)
    assert plan_json["statements"][0]["preconditions"] == [
        {
            "kind": "table_is_empty",
            "schema_name": "public",
            "table_name": "accounts",
        }
    ]

    try:
        async with sessions() as session:
            server_version_num = int(
                await session.scalar(
                    text("SELECT current_setting('server_version_num')")
                )
            )
            assert server_version_num // 10_000 == expected_major
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
                    model_json=target_model,
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

            signal_lease_token = uuid.uuid4()
            attempt_claim = await acquire_migration_run_attempt(
                session,
                migration_run_uuid=first.migration_run_uuid,
                worker_identity="postgres-matrix-worker",
                signal_lease_token=signal_lease_token,
                lease_seconds=60,
                now=now + dt.timedelta(seconds=2),
            )
            await session.flush()
            persisted_attempt = await session.scalar(
                select(MigrationRunAttempt).where(
                    MigrationRunAttempt.migration_run_attempt_uuid
                    == attempt_claim.migration_run_attempt_uuid
                )
            )
            assert persisted_attempt is not None
            assert persisted_attempt.status == "active"
            assert persisted_attempt.attempt_number == 1
            assert persisted_attempt.worker_identity_hash != (
                "postgres-matrix-worker"
            )
            assert persisted_attempt.signal_lease_token_hash != str(
                signal_lease_token
            )
            assert await renew_migration_run_attempt(
                session,
                claim=attempt_claim,
                worker_identity="postgres-matrix-worker",
                signal_lease_token=uuid.uuid4(),
                lease_seconds=60,
                now=now + dt.timedelta(seconds=3),
            ) is False
            assert await renew_migration_run_attempt(
                session,
                claim=attempt_claim,
                worker_identity="postgres-matrix-worker",
                signal_lease_token=signal_lease_token,
                lease_seconds=60,
                now=now + dt.timedelta(seconds=3),
            ) is True
            await transition_migration_run(
                session,
                migration_run_uuid=first.migration_run_uuid,
                expected_state_version=1,
                next_state="sandbox_running",
                event_type="sandbox_started",
                evidence={"postgresql_major": expected_major},
                actor_user_uuid=None,
                now=now + dt.timedelta(seconds=4),
            )
            await session.flush()
            await complete_isolated_dry_run(
                session,
                migration_run_uuid=first.migration_run_uuid,
                expected_state_version=2,
                result={
                    "postgresql_major": expected_major,
                    "statement_count": len(plan.plan_json["statements"]),
                    "base_digest": plan.base_digest,
                    "target_digest": plan.target_digest,
                    "converged": True,
                },
                actor_user_uuid=None,
                now=now + dt.timedelta(seconds=5),
            )
            await session.flush()
            await complete_live_preflight(
                session,
                migration_run_uuid=first.migration_run_uuid,
                expected_state_version=3,
                result={
                    "preconditions_passed": True,
                    "checks": [
                        {
                            "statement_index": 0,
                            "precondition_index": 0,
                            "kind": "table_is_empty",
                            "passed": True,
                        }
                    ],
                    "observed_base_digest": plan.base_digest,
                    "matches_plan_base": True,
                },
                actor_user_uuid=None,
                now=now + dt.timedelta(seconds=6),
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
            assert await renew_migration_run_attempt(
                session,
                claim=attempt_claim,
                worker_identity="postgres-matrix-worker",
                signal_lease_token=signal_lease_token,
                lease_seconds=60,
                now=now + dt.timedelta(seconds=7),
            ) is False
            assert await finish_migration_run_attempt(
                session,
                claim=attempt_claim,
                worker_identity="postgres-matrix-worker",
                signal_lease_token=signal_lease_token,
                succeeded=True,
                now=now + dt.timedelta(seconds=7),
            ) is True
            await session.refresh(persisted_attempt)
            assert persisted_attempt.status == "completed"
            assert persisted_attempt.finished_at == now + dt.timedelta(seconds=7)
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
            assert await session.scalar(
                select(func.count(MigrationRunAttempt.migration_run_uuid)).where(
                    MigrationRunAttempt.migration_run_uuid
                    == first.migration_run_uuid
                )
            ) == 0
    finally:
        await engine.dispose()
