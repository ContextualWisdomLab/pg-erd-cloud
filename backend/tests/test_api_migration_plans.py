from __future__ import annotations

import datetime as dt
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import UniqueConstraint

from app.api.migration_plans import MAX_PLAN_STATEMENTS, create_migration_plan
from app.auth import CurrentUser
from app.models import MigrationPlan
from app.schemas import MigrationPlanCreateIn


def _user() -> CurrentUser:
    return CurrentUser(uuid.uuid4(), "planner", "Planner")


def _model() -> dict:
    return {"format_version": 1, "postgresql_major": 18, "schemas": []}


class FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.scalar = AsyncMock(return_value=None)
        self.flush = AsyncMock()
        self.commit = AsyncMock()
        self.rollback = AsyncMock()

    def add(self, value: object) -> None:
        self.added.append(value)


def _inputs() -> tuple:
    project_uuid = uuid.uuid4()
    connection_uuid = uuid.uuid4()
    snapshot_uuid = uuid.uuid4()
    model_uuid = uuid.uuid4()
    model = SimpleNamespace(
        schema_model_uuid=model_uuid, project_space_uuid=project_uuid
    )
    revision = SimpleNamespace(
        schema_model_revision_uuid=uuid.uuid4(),
        schema_model_uuid=model_uuid,
        revision_digest="a" * 64,
        model_json=_model(),
    )
    connection = SimpleNamespace(
        db_connection_uuid=connection_uuid, project_space_uuid=project_uuid
    )
    snapshot = SimpleNamespace(
        schema_snapshot_uuid=snapshot_uuid,
        project_space_uuid=project_uuid,
        db_connection_uuid=connection_uuid,
        status="succeeded",
    )
    snapshot_data = SimpleNamespace(snapshot_json={"snapshot_contract_version": 1, "server_version": "18.2", "relations": [], "columns": [], "pk_columns": [], "fk_edges": [], "indexes": []})
    return model, revision, connection, snapshot, snapshot_data


@pytest.mark.asyncio
async def test_create_migration_plan_binds_revision_connection_snapshot_and_hashes() -> None:
    inputs = _inputs()
    _, revision, connection, snapshot, _ = inputs
    session = FakeSession()
    user = _user()
    run_sync = AsyncMock(side_effect=lambda function, *args: function(*args))
    with patch(
        "app.api.migration_plans._load_plan_inputs",
        new=AsyncMock(return_value=inputs),
    ), patch(
        "app.api.migration_plans.require_project_member", new_callable=AsyncMock
    ) as membership, patch(
        "app.api.migration_plans.anyio.to_thread.run_sync", new=run_sync
    ):
        out = await create_migration_plan(
            schema_model_revision_uuid=revision.schema_model_revision_uuid,
            body=MigrationPlanCreateIn(
                db_connection_uuid=connection.db_connection_uuid,
                base_schema_snapshot_uuid=snapshot.schema_snapshot_uuid,
            ),
            user=user,
            session=session,
        )

    stored = next(item for item in session.added if isinstance(item, MigrationPlan))
    assert stored.schema_model_revision_uuid == revision.schema_model_revision_uuid
    assert stored.db_connection_uuid == connection.db_connection_uuid
    assert stored.base_schema_snapshot_uuid == snapshot.schema_snapshot_uuid
    assert stored.statement_digest == out.plan_digest
    assert stored.compiler_version == "pg-erd-forward/v1"
    assert out.can_dry_run is True
    assert out.proposed_statements == []
    membership.assert_awaited_once()
    run_sync.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_migration_plan_rejects_cross_project_binding() -> None:
    model, revision, connection, snapshot, snapshot_data = _inputs()
    connection.project_space_uuid = uuid.uuid4()
    with patch(
        "app.api.migration_plans._load_plan_inputs",
        new=AsyncMock(
            return_value=(model, revision, connection, snapshot, snapshot_data)
        ),
    ), patch(
        "app.api.migration_plans.require_project_member", new_callable=AsyncMock
    ):
        with pytest.raises(HTTPException) as exc_info:
            await create_migration_plan(
                schema_model_revision_uuid=revision.schema_model_revision_uuid,
                body=MigrationPlanCreateIn(
                    db_connection_uuid=connection.db_connection_uuid,
                    base_schema_snapshot_uuid=snapshot.schema_snapshot_uuid,
                ),
                user=_user(),
                session=FakeSession(),
            )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "migration plan input not found"


def test_migration_plans_do_not_use_plan_digest_as_database_idempotency_key() -> None:
    """The same SQL may be planned for two targets or recreated after expiry."""
    unique_column_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in MigrationPlan.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("project_space_uuid", "statement_digest") not in unique_column_sets
    assert (
        "schema_model_revision_uuid",
        "db_connection_uuid",
        "base_schema_snapshot_uuid",
        "statement_digest",
    ) in unique_column_sets
    assert ("expires_at",) in {
        tuple(column.name for column in index.columns)
        for index in MigrationPlan.__table__.indexes
    }


@pytest.mark.asyncio
async def test_create_migration_plan_reuses_unexpired_immutable_identity() -> None:
    inputs = _inputs()
    _, revision, connection, snapshot, _ = inputs
    existing = SimpleNamespace(
        migration_plan_uuid=uuid.uuid4(),
        statement_digest="c" * 64,
        base_digest="a" * 64,
        target_digest="b" * 64,
        compiler_version="pg-erd-forward/v1",
        plan_json={
            "statements": [],
            "proposed_statements": [],
            "blockers": [],
            "risk_summary": {"safe": 0, "warning": 0, "destructive": 0},
            "can_dry_run": True,
            "requires_destructive_confirmation": False,
        },
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1),
    )
    compiled = {
        "compiler_version": "pg-erd-forward/v1",
        "base_digest": "a" * 64,
        "target_digest": "b" * 64,
        "plan_digest": "c" * 64,
        "statements": [],
        "proposed_statements": [],
        "blockers": [],
        "risk_summary": {"safe": 0, "warning": 0, "destructive": 0},
        "can_dry_run": True,
        "requires_destructive_confirmation": False,
    }
    session = FakeSession()

    with patch(
        "app.api.migration_plans._load_plan_inputs",
        new=AsyncMock(return_value=inputs),
    ), patch(
        "app.api.migration_plans.require_project_member", new_callable=AsyncMock
    ), patch(
        "app.api.migration_plans.compile_migration_plan", return_value=compiled
    ), patch(
        "app.api.migration_plans._existing_plan",
        new=AsyncMock(return_value=existing),
    ):
        out = await create_migration_plan(
            schema_model_revision_uuid=revision.schema_model_revision_uuid,
            body=MigrationPlanCreateIn(
                db_connection_uuid=connection.db_connection_uuid,
                base_schema_snapshot_uuid=snapshot.schema_snapshot_uuid,
            ),
            user=_user(),
            session=session,
        )

    assert out.migration_plan_uuid == existing.migration_plan_uuid
    assert session.added == []
    session.flush.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_migration_plan_masks_non_member_as_not_found() -> None:
    inputs = _inputs()
    _, revision, connection, snapshot, _ = inputs
    denied = HTTPException(status_code=403, detail="project access denied")

    with patch(
        "app.api.migration_plans._load_plan_inputs",
        new=AsyncMock(return_value=inputs),
    ), patch(
        "app.api.migration_plans.require_project_member",
        new=AsyncMock(side_effect=denied),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await create_migration_plan(
                schema_model_revision_uuid=revision.schema_model_revision_uuid,
                body=MigrationPlanCreateIn(
                    db_connection_uuid=connection.db_connection_uuid,
                    base_schema_snapshot_uuid=snapshot.schema_snapshot_uuid,
                ),
                user=_user(),
                session=FakeSession(),
            )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "migration plan input not found"


@pytest.mark.asyncio
async def test_create_migration_plan_rejects_excessive_statement_count() -> None:
    inputs = _inputs()
    _, revision, connection, snapshot, _ = inputs
    compiled = {
        "compiler_version": "pg-erd-forward/v1",
        "base_digest": "a" * 64,
        "target_digest": "b" * 64,
        "plan_digest": "c" * 64,
        "statements": [{} for _ in range(MAX_PLAN_STATEMENTS + 1)],
        "blockers": [],
        "risk_summary": {"safe": 0, "warning": 0, "destructive": 0},
        "can_dry_run": True,
        "requires_destructive_confirmation": False,
    }
    session = FakeSession()

    with patch(
        "app.api.migration_plans._load_plan_inputs",
        new=AsyncMock(return_value=inputs),
    ), patch(
        "app.api.migration_plans.require_project_member", new_callable=AsyncMock
    ), patch(
        "app.api.migration_plans.compile_migration_plan", return_value=compiled
    ):
        with pytest.raises(HTTPException) as exc_info:
            await create_migration_plan(
                schema_model_revision_uuid=revision.schema_model_revision_uuid,
                body=MigrationPlanCreateIn(
                    db_connection_uuid=connection.db_connection_uuid,
                    base_schema_snapshot_uuid=snapshot.schema_snapshot_uuid,
                ),
                user=_user(),
                session=session,
            )

    assert exc_info.value.status_code == 413
    assert exc_info.value.detail == "migration plan is too large"
    assert session.added == []


@pytest.mark.asyncio
async def test_create_migration_plan_counts_review_only_proposals_toward_limit() -> None:
    inputs = _inputs()
    _, revision, connection, snapshot, _ = inputs
    compiled = {
        "compiler_version": "pg-erd-forward/v1",
        "base_digest": "a" * 64,
        "target_digest": "b" * 64,
        "plan_digest": "c" * 64,
        "statements": [],
        "proposed_statements": [{} for _ in range(MAX_PLAN_STATEMENTS + 1)],
        "blockers": [{"code": "blocked"}],
        "risk_summary": {"safe": 0, "warning": 0, "destructive": 0},
        "can_dry_run": False,
        "requires_destructive_confirmation": False,
    }

    with patch(
        "app.api.migration_plans._load_plan_inputs",
        new=AsyncMock(return_value=inputs),
    ), patch(
        "app.api.migration_plans.require_project_member", new_callable=AsyncMock
    ), patch(
        "app.api.migration_plans.compile_migration_plan", return_value=compiled
    ):
        with pytest.raises(HTTPException) as exc_info:
            await create_migration_plan(
                schema_model_revision_uuid=revision.schema_model_revision_uuid,
                body=MigrationPlanCreateIn(
                    db_connection_uuid=connection.db_connection_uuid,
                    base_schema_snapshot_uuid=snapshot.schema_snapshot_uuid,
                ),
                user=_user(),
                session=FakeSession(),
            )

    assert exc_info.value.status_code == 413
