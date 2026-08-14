"""Real-PostgreSQL migration-run/outbox and live-read integration acceptance."""

from __future__ import annotations

import asyncio
import copy
import datetime as dt
import os
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import cast
from urllib.parse import urlparse

import asyncpg
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.forward.isolated_dry_run import (
    IsolatedPostgresConnection,
    execute_isolated_dry_run,
)
from app.forward.migration_plan import compile_migration_plan
from app.forward.live_preflight import (
    LivePreflightContractError,
    execute_bound_live_preflight,
    execute_live_preflight,
)
from app.forward.migration_run import (
    MigrationRunAttemptClaim,
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
from app.jobs import valkey_queue
from app.jobs.migration_run_consumer import (
    MigrationRunConsumerError,
    make_attempt_bound_migration_run_handler,
    process_one_migration_run_signal,
)
from app.jobs.migration_dry_run_worker import (
    IsolatedSandboxExecution,
    IsolatedSandboxRequest,
    LivePreflightExecution,
    LivePreflightRequest,
    MigrationDryRunWorkerError,
    make_durable_dry_run_attempt_handler,
)
from app.jobs.valkey_queue import MigrationRunSignalClaim
from app.settings import settings

_POSTGRES_URL = os.getenv("POSTGRES_INTEGRATION_URL")
_POSTGRES_SANDBOX_URL = os.getenv("POSTGRES_SANDBOX_INTEGRATION_URL")
_POSTGRES_TARGET_URL = os.getenv("POSTGRES_TARGET_INTEGRATION_URL")
_POSTGRES_PREFLIGHT_URL = os.getenv("POSTGRES_PREFLIGHT_INTEGRATION_URL")
_VALKEY_URL = os.getenv("VALKEY_INTEGRATION_URL")
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


async def _delete_project_fixture(
    session: AsyncSession, *, project_space_uuid: uuid.UUID
) -> None:
    """Delete one committed integration fixture in restrictive-FK order."""

    parameters = {"project_space_uuid": project_space_uuid}
    await session.execute(
        text(
            "DELETE FROM migration_run "
            "WHERE project_space_uuid = :project_space_uuid"
        ),
        parameters,
    )
    await session.execute(
        text(
            "DELETE FROM migration_plan "
            "WHERE project_space_uuid = :project_space_uuid"
        ),
        parameters,
    )
    await session.execute(
        text(
            "DELETE FROM schema_model_revision "
            "WHERE schema_model_uuid IN ("
            "SELECT schema_model_uuid FROM schema_model "
            "WHERE project_space_uuid = :project_space_uuid"
            ")"
        ),
        parameters,
    )
    await session.execute(
        text(
            "DELETE FROM project_space "
            "WHERE project_space_uuid = :project_space_uuid"
        ),
        parameters,
    )


@pytest.mark.asyncio
async def test_real_postgres_persists_terminal_cancellation_state_contract() -> None:
    """Verify migration checks admit cancellation in runs and event history."""

    connection = await asyncpg.connect(_asyncpg_url())
    try:
        rows = await connection.fetch(
            "SELECT conname, pg_get_constraintdef(oid) AS definition "
            "FROM pg_catalog.pg_constraint "
            "WHERE conname = ANY($1::text[]) ORDER BY conname",
            [
                "ck_migration_run__state",
                "ck_migration_run__kind_state",
                "ck_migration_run_event__state_before",
                "ck_migration_run_event__state_after",
            ],
        )
        definitions = {
            str(row["conname"]): str(row["definition"]) for row in rows
        }
        assert set(definitions) == {
            "ck_migration_run__state",
            "ck_migration_run__kind_state",
            "ck_migration_run_event__state_before",
            "ck_migration_run_event__state_after",
        }
        assert all(
            "cancelled" in definition for definition in definitions.values()
        )
        assert definitions["ck_migration_run__kind_state"].count(
            "cancelled"
        ) == 2
    finally:
        await connection.close()


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
    connection: asyncpg.Connection[asyncpg.Record],
    schema_name: str,
    *,
    stage_evidence: list[str] | None = None,
) -> dict[str, object]:
    """Capture the strict capability rows from the owned sandbox connection."""

    include_system = False

    def mark(stage: str) -> None:
        if stage_evidence is not None:
            stage_evidence.append(stage)

    async def fetch_rows(label: str, query: str) -> list[dict[str, object]]:
        mark(f"capture-{label}-started")
        rows = await connection.fetch(query, schema_name, include_system)
        mark(f"capture-{label}-completed")
        return [dict(row) for row in rows]

    mark("capture-version-started")
    server_version = str(await connection.fetchval("SHOW server_version"))
    mark("capture-version-completed")
    return {
        "snapshot_contract_version": CURRENT_POSTGRES_SNAPSHOT_CONTRACT_VERSION,
        "server_version": server_version,
        "schemas": await fetch_rows("schemas", queries.SCHEMAS_SQL),
        "relations": await fetch_rows("relations", queries.RELATIONS_SQL),
        "columns": await fetch_rows("columns", queries.COLUMNS_SQL),
        "constraints": await fetch_rows("constraints", queries.CONSTRAINTS_SQL),
        "indexes": await fetch_rows("indexes", queries.INDEXES_SQL),
        "pk_columns": await fetch_rows("pk-columns", queries.PK_COLUMNS_SQL),
        "fk_edges": await fetch_rows("fk-edges", queries.FK_EDGES_SQL),
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
            assert privileges is not None
            assert dict(privileges) == {
                "can_create": False,
                "can_temp": False,
            }
            role_attributes = await connection.fetchrow(
                "SELECT rolsuper, rolcreaterole, rolcreatedb, rolreplication, "
                "rolbypassrls FROM pg_catalog.pg_roles WHERE rolname = current_user"
            )
            assert role_attributes is not None
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
                    await admin_connection.execute(
                        "SELECT pg_catalog.pg_stat_clear_snapshot()"
                    )
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
async def test_real_postgres_durable_worker_recovers_without_sandbox_replay() -> None:
    """Resume a crashed durable dry run without replaying committed sandbox DDL."""

    assert _POSTGRES_URL is not None
    assert _POSTGRES_SANDBOX_URL is not None
    assert _POSTGRES_TARGET_URL is not None
    assert _POSTGRES_PREFLIGHT_URL is not None
    assert _EXPECTED_MAJOR is not None
    database_paths = {
        urlparse(_POSTGRES_URL).path,
        urlparse(_POSTGRES_SANDBOX_URL).path,
        urlparse(_POSTGRES_TARGET_URL).path,
    }
    assert len(database_paths) == 3
    major = int(_EXPECTED_MAJOR)
    schema_name = f"Worker Dry Run {uuid.uuid4().hex}"
    table_name = '검증 "테이블"'
    quoted_schema = '"' + schema_name.replace('"', '""') + '"'
    base_model: dict[str, object] = {
        "format_version": 1,
        "postgresql_major": major,
        "schemas": [],
    }
    target_model: dict[str, object] = {
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
                                "column_name": "ID 값",
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
    plan_json = compile_migration_plan(base_model, target_model)
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
    signal_token = uuid.uuid4()
    sandbox_requests: list[IsolatedSandboxRequest] = []
    live_requests: list[LivePreflightRequest] = []
    capability_order: list[str] = []
    sandbox_stages: list[str] = []
    crash_before_first_live_read = True

    @asynccontextmanager
    async def sandbox_factory(
        request: IsolatedSandboxRequest,
    ) -> AsyncIterator[IsolatedSandboxExecution]:
        sandbox_requests.append(request)
        capability_order.append("sandbox-enter")
        sandbox_stages.append("connect-started")
        connection = await asyncpg.connect(_sandbox_asyncpg_url())
        sandbox_stages.append("connected")

        async def capture(
            owned_connection: IsolatedPostgresConnection,
        ) -> dict[str, object]:
            sandbox_stages.append("capture-started")
            snapshot = await _capture_filtered_snapshot(
                cast("asyncpg.Connection[asyncpg.Record]", owned_connection),
                schema_name,
                stage_evidence=sandbox_stages,
            )
            sandbox_stages.append("capture-completed")
            return snapshot

        try:
            yield IsolatedSandboxExecution(connection, capture)
            sandbox_stages.append("execution-completed")
        finally:
            sandbox_stages.append("cleanup-started")
            await connection.execute(
                f"DROP SCHEMA IF EXISTS {quoted_schema} CASCADE"
            )
            await connection.close()
            sandbox_stages.append("cleanup-completed")
            capability_order.append("sandbox-exit")

    @asynccontextmanager
    async def live_factory(
        request: LivePreflightRequest,
    ) -> AsyncIterator[LivePreflightExecution]:
        nonlocal crash_before_first_live_read
        live_requests.append(request)
        if crash_before_first_live_read:
            crash_before_first_live_read = False
            capability_order.append("live-crash")
            raise asyncio.CancelledError
        capability_order.append("live-enter")
        connection = await asyncpg.connect(_preflight_asyncpg_url())

        async def capture(
            owned_connection: asyncpg.Connection[asyncpg.Record],
        ) -> dict[str, object]:
            return await _capture_filtered_snapshot(
                owned_connection, schema_name
            )

        try:
            yield LivePreflightExecution(connection, capture)
        finally:
            await connection.close()
            capability_order.append("live-exit")

    try:
        async with sessions() as setup_session:
            setup_session.add(
                UserAccount(
                    user_account_uuid=user_uuid,
                    oidc_subject=f"durable-worker-integration:{user_uuid}",
                    display_name="Durable worker integration",
                    created_at=now,
                )
            )
            await setup_session.flush()
            setup_session.add(
                ProjectSpace(
                    project_space_uuid=project_uuid,
                    project_name="durable worker integration",
                    created_by_user_uuid=user_uuid,
                    created_at=now,
                )
            )
            await setup_session.flush()
            setup_session.add_all(
                [
                    DbConnection(
                        db_connection_uuid=connection_uuid,
                        project_space_uuid=project_uuid,
                        conn_name="durable worker target",
                        dsn_ciphertext=b"not-used",
                        dsn_nonce=b"not-used",
                        created_at=now,
                        updated_at=now,
                    ),
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
                        model_name="durable_worker_model",
                        current_revision_number=1,
                        created_by_user_uuid=user_uuid,
                        created_at=now,
                        updated_at=now,
                    ),
                ]
            )
            await setup_session.flush()
            setup_session.add(
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
            await setup_session.flush()
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
            setup_session.add(plan)
            await setup_session.flush()
            created = await create_migration_run(
                setup_session,
                plan=plan,
                run_kind="dry_run",
                idempotency_key="real-postgres-durable-worker",
                requested_by_user_uuid=user_uuid,
                evidence={"request_source": "postgresql_matrix"},
                now=now,
            )
            await setup_session.commit()

        async with sessions() as claim_session:
            async with claim_session.begin():
                attempt_claim = await acquire_migration_run_attempt(
                    claim_session,
                    migration_run_uuid=created.migration_run_uuid,
                    worker_identity="crashed-real-postgres-worker",
                    signal_lease_token=signal_token,
                    lease_seconds=1,
                    now=now + dt.timedelta(seconds=1),
                )

        handler = make_durable_dry_run_attempt_handler(
            sandbox_factory,
            live_factory,
            lock_timeout_ms=2_000,
            sandbox_statement_timeout_ms=5_000,
            preflight_statement_timeout_ms=2_000,
        )
        with pytest.raises(asyncio.CancelledError):
            try:
                await handler(
                    sessions,
                    MigrationRunSignalClaim(
                        created.migration_run_uuid, signal_token
                    ),
                    attempt_claim,
                )
            except MigrationDryRunWorkerError as error:
                pytest.fail(
                    "durable sandbox stage failed after fixed evidence "
                    f"{sandbox_stages!r}: {error}"
                )

        recovery_token = uuid.uuid4()
        async with sessions() as recovery_claim_session:
            async with recovery_claim_session.begin():
                recovery_claim = await acquire_migration_run_attempt(
                    recovery_claim_session,
                    migration_run_uuid=created.migration_run_uuid,
                    worker_identity="recovered-real-postgres-worker",
                    signal_lease_token=recovery_token,
                    lease_seconds=60,
                    now=now + dt.timedelta(seconds=3),
                )

        await handler(
            sessions,
            MigrationRunSignalClaim(
                created.migration_run_uuid, recovery_token
            ),
            recovery_claim,
        )

        async with sessions() as finish_session:
            async with finish_session.begin():
                assert await finish_migration_run_attempt(
                    finish_session,
                    claim=recovery_claim,
                    worker_identity="recovered-real-postgres-worker",
                    signal_lease_token=recovery_token,
                    succeeded=True,
                    now=now + dt.timedelta(seconds=4),
                )

        async with sessions() as verify_session:
            persisted_run = await verify_session.get(
                MigrationRun, created.migration_run_uuid
            )
            assert persisted_run is not None
            assert persisted_run.state == "passed"
            assert persisted_run.state_version == 4
            assert persisted_run.observed_base_digest == plan_json["base_digest"]
            assert await verify_session.scalar(
                select(func.count(MigrationRunEvent.migration_run_event_uuid)).where(
                    MigrationRunEvent.migration_run_uuid
                    == created.migration_run_uuid
                )
            ) == 4
            persisted_attempts = list(
                await verify_session.scalars(
                    select(MigrationRunAttempt)
                    .where(
                        MigrationRunAttempt.migration_run_uuid
                        == created.migration_run_uuid
                    )
                    .order_by(MigrationRunAttempt.attempt_number)
                )
            )
            assert [attempt.status for attempt in persisted_attempts] == [
                "abandoned",
                "completed",
            ]
            assert [attempt.acquired_state_version for attempt in persisted_attempts] == [
                1,
                3,
            ]

        assert len(sandbox_requests) == 1
        assert len(live_requests) == 2
        assert sandbox_requests[0].migration_run_attempt_uuid == (
            attempt_claim.migration_run_attempt_uuid
        )
        assert live_requests[0].migration_run_attempt_uuid == (
            attempt_claim.migration_run_attempt_uuid
        )
        assert live_requests[1].migration_run_attempt_uuid == (
            recovery_claim.migration_run_attempt_uuid
        )
        assert not hasattr(sandbox_requests[0], "db_connection_uuid")
        assert all(
            request.db_connection_uuid == connection_uuid
            for request in live_requests
        )
        assert capability_order == [
            "sandbox-enter",
            "sandbox-exit",
            "live-crash",
            "live-enter",
            "live-exit",
        ]
    finally:
        async with sessions() as cleanup_session:
            await _delete_project_fixture(
                cleanup_session, project_space_uuid=project_uuid
            )
            await cleanup_session.execute(
                text(
                    "DELETE FROM user_account "
                    "WHERE user_account_uuid = :user_account_uuid"
                ),
                {"user_account_uuid": user_uuid},
            )
            await cleanup_session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_real_postgres_concurrent_duplicate_apply_intents_choose_one_winner() -> None:
    """Prove concurrent same-key apply requests persist one execution-free intent."""

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
    passed_run_uuid = uuid.uuid4()
    assert _EXPECTED_MAJOR is not None
    base_model, target_model = _migration_models_with_precondition(
        int(_EXPECTED_MAJOR)
    )
    plan_json = compile_migration_plan(base_model, target_model)

    try:
        async with sessions() as setup_session:
            setup_session.add(
                UserAccount(
                    user_account_uuid=user_uuid,
                    oidc_subject=f"concurrent-integration:{user_uuid}",
                    display_name="Concurrent PostgreSQL integration",
                    created_at=now,
                )
            )
            await setup_session.flush()
            setup_session.add(
                ProjectSpace(
                    project_space_uuid=project_uuid,
                    project_name="concurrent migration run integration",
                    created_by_user_uuid=user_uuid,
                    created_at=now,
                )
            )
            await setup_session.flush()
            setup_session.add_all(
                [
                    DbConnection(
                        db_connection_uuid=connection_uuid,
                        project_space_uuid=project_uuid,
                        conn_name="concurrent integration target",
                        dsn_ciphertext=b"not-used",
                        dsn_nonce=b"not-used",
                        created_at=now,
                        updated_at=now,
                    ),
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
                        model_name="concurrent_integration_model",
                        current_revision_number=1,
                        created_by_user_uuid=user_uuid,
                        created_at=now,
                        updated_at=now,
                    ),
                ]
            )
            await setup_session.flush()
            setup_session.add(
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
            await setup_session.flush()
            setup_session.add(
                MigrationPlan(
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
            )
            setup_session.add(
                MigrationRun(
                    migration_run_uuid=passed_run_uuid,
                    project_space_uuid=project_uuid,
                    migration_plan_uuid=plan_uuid,
                    passed_dry_run_uuid=None,
                    run_kind="dry_run",
                    state="passed",
                    state_version=1,
                    idempotency_key_hash="a" * 64,
                    plan_digest=plan_json["plan_digest"],
                    request_digest="b" * 64,
                    confirmation_digest=None,
                    destructive_confirmation=None,
                    latest_event_digest="c" * 64,
                    requested_by_user_uuid=user_uuid,
                    cancellation_requested=False,
                    observed_base_digest=plan_json["base_digest"],
                    evidence_json={},
                    error_code=None,
                    created_at=now,
                    updated_at=now,
                    started_at=now,
                    finished_at=now,
                )
            )
            await setup_session.commit()

        first_session = sessions()
        second_session = sessions()
        try:
            first_plan = await first_session.get(MigrationPlan, plan_uuid)
            second_plan = await second_session.get(MigrationPlan, plan_uuid)
            first_passed_run = await first_session.get(
                MigrationRun, passed_run_uuid
            )
            second_passed_run = await second_session.get(
                MigrationRun, passed_run_uuid
            )
            first_connection = await first_session.get(
                DbConnection, connection_uuid
            )
            second_connection = await second_session.get(
                DbConnection, connection_uuid
            )
            first_revision = await first_session.get(
                SchemaModelRevision, revision_uuid
            )
            second_revision = await second_session.get(
                SchemaModelRevision, revision_uuid
            )
            first_model = await first_session.get(SchemaModel, model_uuid)
            second_model = await second_session.get(SchemaModel, model_uuid)
            assert first_plan is not None
            assert second_plan is not None
            assert first_passed_run is not None
            assert second_passed_run is not None
            assert first_connection is not None
            assert second_connection is not None
            assert first_revision is not None
            assert second_revision is not None
            assert first_model is not None
            assert second_model is not None
            second_backend_pid = await second_session.scalar(
                text("SELECT pg_backend_pid()")
            )
            assert isinstance(second_backend_pid, int)
            first = await create_migration_run(
                first_session,
                plan=first_plan,
                run_kind="apply",
                idempotency_key="concurrent-real-postgres-apply-key",
                requested_by_user_uuid=user_uuid,
                evidence={"request_source": "concurrent_postgresql_matrix"},
                passed_dry_run=first_passed_run,
                connection=first_connection,
                typed_connection_name=first_connection.conn_name,
                destructive_acknowledged=bool(
                    plan_json["requires_destructive_confirmation"]
                ),
                model_revision=first_revision,
                schema_model=first_model,
                now=now,
            )
            await first_session.flush()
            second_task = asyncio.create_task(
                create_migration_run(
                    second_session,
                    plan=second_plan,
                    run_kind="apply",
                    idempotency_key="concurrent-real-postgres-apply-key",
                    requested_by_user_uuid=user_uuid,
                    evidence={
                        "request_source": "concurrent_postgresql_matrix"
                    },
                    passed_dry_run=second_passed_run,
                    connection=second_connection,
                    typed_connection_name=second_connection.conn_name,
                    destructive_acknowledged=bool(
                        plan_json["requires_destructive_confirmation"]
                    ),
                    model_revision=second_revision,
                    schema_model=second_model,
                    now=now,
                )
            )
            async with sessions() as observer_session:
                for _ in range(500):
                    waiting_on_winner = await observer_session.scalar(
                        text(
                            "SELECT EXISTS ("
                            "SELECT 1 FROM pg_catalog.pg_stat_activity "
                            "WHERE pid = :pid AND wait_event_type = 'Lock'"
                            ")"
                        ),
                        {"pid": second_backend_pid},
                    )
                    if waiting_on_winner:
                        break
                    assert not second_task.done(), (
                        "duplicate insert completed before the winner committed"
                    )
                    await asyncio.sleep(0.01)
                else:
                    pytest.fail(
                        "duplicate insert did not wait on the concurrent winner"
                    )
            await first_session.commit()
            second = await asyncio.wait_for(second_task, timeout=5)
            await second_session.commit()
        finally:
            await first_session.close()
            await second_session.close()

        assert second.reused is True
        assert second.migration_run_uuid == first.migration_run_uuid
        async with sessions() as verify_session:
            assert await verify_session.scalar(
                select(func.count(MigrationRun.migration_run_uuid)).where(
                    MigrationRun.project_space_uuid == project_uuid,
                    MigrationRun.run_kind == "apply",
                )
            ) == 1
            assert await verify_session.scalar(
                select(func.count(MigrationRunEvent.migration_run_event_uuid)).where(
                    MigrationRunEvent.migration_run_uuid
                    == first.migration_run_uuid
                )
            ) == 1
            assert await verify_session.scalar(
                select(func.count(MigrationRunDispatch.migration_run_uuid)).where(
                    MigrationRunDispatch.migration_run_uuid
                    == first.migration_run_uuid
                )
            ) == 0
    finally:
        async with sessions() as cleanup_session:
            await _delete_project_fixture(
                cleanup_session, project_space_uuid=project_uuid
            )
            await cleanup_session.execute(
                text(
                    "DELETE FROM user_account "
                    "WHERE user_account_uuid = :user_account_uuid"
                ),
                {"user_account_uuid": user_uuid},
            )
            await cleanup_session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_real_postgres_and_valkey_recover_failure_and_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove dual-lease failure/retry and crash takeover across both stores."""

    assert _POSTGRES_URL is not None
    if not _VALKEY_URL:
        pytest.skip("VALKEY_INTEGRATION_URL is not configured")
    engine = create_async_engine(_POSTGRES_URL)
    connection = await engine.connect()
    outer_transaction = await connection.begin()
    sessions = async_sessionmaker(
        connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
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

    suffix = uuid.uuid4().hex
    queue_key = f"pg-erd-cloud:test:migration:{suffix}"
    processing_key = f"pg-erd-cloud:test:migration-processing:{suffix}"
    lease_token_key = f"pg-erd-cloud:test:migration-lease:{suffix}"
    monkeypatch.setattr(settings, "job_queue_backend", "valkey")
    monkeypatch.setattr(settings, "valkey_url", _VALKEY_URL)
    monkeypatch.setattr(settings, "valkey_sentinel_hosts", None)
    monkeypatch.setattr(settings, "valkey_migration_run_queue_key", queue_key)
    monkeypatch.setattr(
        settings, "valkey_migration_run_processing_key", processing_key
    )
    monkeypatch.setattr(
        settings, "valkey_migration_run_lease_token_key", lease_token_key
    )
    redis_asyncio = valkey_queue._load_redis_module()
    client = redis_asyncio.from_url(_VALKEY_URL)

    try:
        await client.delete(queue_key, processing_key, lease_token_key)
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

            await session.commit()
            assert await valkey_queue.enqueue_migration_run_signal(
                first.migration_run_uuid, now + dt.timedelta(seconds=2)
            )
            handler_calls = 0
            secret = "postgresql://owner:secret@target/private"

            async def fail_then_succeed(*_args: object) -> None:
                nonlocal handler_calls
                handler_calls += 1
                if handler_calls == 1:
                    raise RuntimeError(secret)

            handler = make_attempt_bound_migration_run_handler(
                fail_then_succeed,
                worker_identity="composed-postgres-valkey-worker",
                attempt_lease_seconds=60,
            )
            with pytest.raises(MigrationRunConsumerError) as failed:
                await process_one_migration_run_signal(
                    sessions,
                    handler,
                    now=now + dt.timedelta(seconds=2),
                    retry_delay_s=1,
                )
            assert str(failed.value) == "migration run handler failed"
            assert secret not in repr(failed.value)
            assert await process_one_migration_run_signal(
                sessions,
                handler,
                now=now + dt.timedelta(seconds=3),
                retry_delay_s=1,
            )
            assert handler_calls == 2
            persisted_consumer_attempts = list(
                await session.scalars(
                    select(MigrationRunAttempt)
                    .where(
                        MigrationRunAttempt.migration_run_uuid
                        == first.migration_run_uuid
                    )
                    .order_by(MigrationRunAttempt.attempt_number)
                )
            )
            assert [attempt.status for attempt in persisted_consumer_attempts] == [
                "abandoned",
                "completed",
            ]
            assert [attempt.attempt_number for attempt in persisted_consumer_attempts] == [
                1,
                2,
            ]
            assert all(
                len(attempt.worker_identity_hash) == 64
                and len(attempt.signal_lease_token_hash) == 64
                for attempt in persisted_consumer_attempts
            )
            assert await client.zrange(queue_key, 0, -1) == []
            assert await client.zrange(processing_key, 0, -1) == []
            assert await client.hlen(lease_token_key) == 0

            crash_started_at = dt.datetime.now(dt.timezone.utc)
            assert await valkey_queue.enqueue_migration_run_signal(
                first.migration_run_uuid, crash_started_at
            )
            crash_signal_claim = await valkey_queue.claim_due_migration_run_signal(
                now=crash_started_at,
                lease_seconds=1,
            )
            assert crash_signal_claim is not None
            async with sessions() as crash_session:
                async with crash_session.begin():
                    crash_attempt_claim = await acquire_migration_run_attempt(
                        crash_session,
                        migration_run_uuid=first.migration_run_uuid,
                        worker_identity="crashed-postgres-valkey-worker",
                        signal_lease_token=crash_signal_claim.lease_token,
                        lease_seconds=1,
                        now=crash_started_at,
                    )
                    assert await renew_migration_run_attempt(
                        crash_session,
                        claim=crash_attempt_claim,
                        worker_identity="crashed-postgres-valkey-worker",
                        signal_lease_token=uuid.uuid4(),
                        lease_seconds=1,
                        now=crash_started_at,
                    ) is False

            await asyncio.sleep(1.1)
            assert not await valkey_queue.renew_migration_run_signal(
                crash_signal_claim,
                now=dt.datetime.now(dt.timezone.utc),
                lease_seconds=60,
            )
            recovered_attempts: list[MigrationRunAttemptClaim] = []
            recovered_signals: list[valkey_queue.MigrationRunSignalClaim] = []

            async def recover_to_pass(
                factory: Callable[[], AsyncSession],
                recovered_signal: valkey_queue.MigrationRunSignalClaim,
                recovered_attempt: MigrationRunAttemptClaim,
            ) -> None:
                recovered_signals.append(recovered_signal)
                recovered_attempts.append(recovered_attempt)
                async with factory() as worker_session:
                    async with worker_session.begin():
                        await transition_migration_run(
                            worker_session,
                            migration_run_uuid=first.migration_run_uuid,
                            expected_state_version=1,
                            next_state="sandbox_running",
                            event_type="sandbox_started",
                            evidence={"postgresql_major": expected_major},
                            actor_user_uuid=None,
                        )
                async with factory() as worker_session:
                    async with worker_session.begin():
                        await complete_isolated_dry_run(
                            worker_session,
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
                        )
                async with factory() as worker_session:
                    async with worker_session.begin():
                        await complete_live_preflight(
                            worker_session,
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
                        )

            recovery_handler = make_attempt_bound_migration_run_handler(
                recover_to_pass,
                worker_identity="recovered-postgres-valkey-worker",
                attempt_lease_seconds=60,
            )
            recovery_time = dt.datetime.now(dt.timezone.utc)
            assert await process_one_migration_run_signal(
                sessions,
                recovery_handler,
                now=recovery_time,
            )
            assert len(recovered_attempts) == 1
            assert len(recovered_signals) == 1
            assert recovered_signals[0].lease_token != crash_signal_claim.lease_token
            assert not await valkey_queue.ack_migration_run_signal(
                crash_signal_claim
            )

            persisted_attempts = list(
                await session.scalars(
                    select(MigrationRunAttempt)
                    .where(
                        MigrationRunAttempt.migration_run_uuid
                        == first.migration_run_uuid
                    )
                    .order_by(MigrationRunAttempt.attempt_number)
                )
            )
            assert [attempt.attempt_number for attempt in persisted_attempts] == [
                1,
                2,
                3,
                4,
            ]
            assert [attempt.status for attempt in persisted_attempts] == [
                "abandoned",
                "completed",
                "abandoned",
                "completed",
            ]
            assert all(
                len(attempt.worker_identity_hash) == 64
                and len(attempt.signal_lease_token_hash) == 64
                for attempt in persisted_attempts
            )
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
                claim=recovered_attempts[0],
                worker_identity="recovered-postgres-valkey-worker",
                signal_lease_token=recovered_signals[0].lease_token,
                lease_seconds=60,
                now=dt.datetime.now(dt.timezone.utc),
            ) is False
            assert await finish_migration_run_attempt(
                session,
                claim=recovered_attempts[0],
                worker_identity="recovered-postgres-valkey-worker",
                signal_lease_token=recovered_signals[0].lease_token,
                succeeded=True,
                now=dt.datetime.now(dt.timezone.utc),
            ) is False
            assert await session.scalar(
                select(func.count(MigrationRunEvent.migration_run_event_uuid)).where(
                    MigrationRunEvent.migration_run_uuid == first.migration_run_uuid
                )
            ) == 4
            assert await client.zrange(queue_key, 0, -1) == []
            assert await client.zrange(processing_key, 0, -1) == []
            assert await client.hlen(lease_token_key) == 0

            target_connection = await session.get(DbConnection, connection_uuid)
            assert target_connection is not None
            model_revision = await session.get(
                SchemaModelRevision, plan.schema_model_revision_uuid
            )
            assert model_revision is not None
            schema_model = await session.get(
                SchemaModel,
                model_revision.schema_model_uuid,
                with_for_update=True,
            )
            assert schema_model is not None
            apply_intent = await create_migration_run(
                session,
                plan=plan,
                run_kind="apply",
                idempotency_key="real-postgres-apply-intent",
                requested_by_user_uuid=user_uuid,
                evidence={"request_source": "postgresql_matrix"},
                passed_dry_run=persisted_run,
                connection=target_connection,
                typed_connection_name="integration target",
                destructive_acknowledged=False,
                model_revision=model_revision,
                schema_model=schema_model,
                now=dt.datetime.now(dt.timezone.utc),
            )
            await session.flush()
            persisted_apply = await session.get(
                MigrationRun, apply_intent.migration_run_uuid
            )
            assert persisted_apply is not None
            assert persisted_apply.run_kind == "apply"
            assert persisted_apply.state == "queued"
            assert persisted_apply.passed_dry_run_uuid == first.migration_run_uuid
            assert len(persisted_apply.confirmation_digest or "") == 64
            assert persisted_apply.destructive_confirmation is False
            assert await session.scalar(
                select(func.count(MigrationRunDispatch.migration_run_uuid)).where(
                    MigrationRunDispatch.migration_run_uuid
                    == apply_intent.migration_run_uuid
                )
            ) == 0

            await session.commit()

        await outer_transaction.rollback()

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
        if outer_transaction.is_active:
            await outer_transaction.rollback()
        await client.delete(queue_key, processing_key, lease_token_key)
        await valkey_queue._close_client(client)
        await connection.close()
        await engine.dispose()
