from __future__ import annotations

import datetime as dt
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import UniqueConstraint
from sqlalchemy.exc import IntegrityError

from app.api.migration_plans import (
    EXPIRED_PLAN_RETENTION,
    MAX_PLAN_STATEMENTS,
    _cleanup_expired_unreferenced_plans,
    _load_plan_inputs,
    create_migration_plan,
    get_migration_plan,
)
from app.auth import CurrentUser
from app.forward.migration_plan import compile_migration_plan
from app.forward.schema_model import SchemaModelValidationError
from app.models import MigrationPlan
from app.schemas import MigrationPlanCreateIn, MigrationPlanOut


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
        self.get = AsyncMock(return_value=None)
        self.execute = AsyncMock(return_value=SimpleNamespace(rowcount=0))

    def add(self, value: object) -> None:
        self.added.append(value)


def _stored_plan() -> SimpleNamespace:
    plan_json = compile_migration_plan(_model(), _model())
    return SimpleNamespace(
        migration_plan_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        schema_model_revision_uuid=uuid.uuid4(),
        db_connection_uuid=uuid.uuid4(),
        base_schema_snapshot_uuid=uuid.uuid4(),
        statement_digest=plan_json["plan_digest"],
        base_digest=plan_json["base_digest"],
        target_digest=plan_json["target_digest"],
        compiler_version=plan_json["compiler_version"],
        plan_json=plan_json,
        created_by_user_uuid=uuid.uuid4(),
        created_at=dt.datetime.now(dt.timezone.utc),
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1),
    )


@pytest.mark.asyncio
async def test_get_migration_plan_returns_immutable_member_preview() -> None:
    plan = _stored_plan()
    session = FakeSession()
    session.get.return_value = plan

    with patch(
        "app.api.migration_plans.require_project_member", new_callable=AsyncMock
    ) as membership:
        out = await get_migration_plan(
            migration_plan_uuid=plan.migration_plan_uuid,
            user=_user(),
            session=session,
        )

    assert out.migration_plan_uuid == plan.migration_plan_uuid
    assert out.plan_digest == plan.statement_digest
    assert out.project_space_uuid == plan.project_space_uuid
    assert out.schema_model_revision_uuid == plan.schema_model_revision_uuid
    assert out.db_connection_uuid == plan.db_connection_uuid
    assert out.base_schema_snapshot_uuid == plan.base_schema_snapshot_uuid
    assert out.snapshot_contract_version == 1
    assert out.postgresql_major == 18
    assert out.created_by_user_uuid == plan.created_by_user_uuid
    assert out.created_at == plan.created_at
    membership.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_migration_plan_rejects_tampered_persisted_payload() -> None:
    plan = _stored_plan()
    plan.plan_json["can_dry_run"] = False
    session = FakeSession()
    session.get.return_value = plan

    with patch(
        "app.api.migration_plans.require_project_member", new_callable=AsyncMock
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_migration_plan(
                migration_plan_uuid=plan.migration_plan_uuid,
                user=_user(),
                session=session,
            )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "migration plan integrity verification failed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("compiler_version", "pg-erd-forward/tampered"),
        ("base_digest", "0" * 64),
        ("target_digest", "0" * 64),
    ],
)
async def test_get_migration_plan_rejects_denormalized_binding_mismatch(
    field: str, value: str
) -> None:
    plan = _stored_plan()
    setattr(plan, field, value)
    session = FakeSession()
    session.get.return_value = plan

    with patch(
        "app.api.migration_plans.require_project_member", new_callable=AsyncMock
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_migration_plan(
                migration_plan_uuid=plan.migration_plan_uuid,
                user=_user(),
                session=session,
            )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "migration plan integrity verification failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", [True, False])
async def test_get_migration_plan_masks_missing_and_non_member_identity(
    missing: bool,
) -> None:
    plan = _stored_plan()
    session = FakeSession()
    session.get.return_value = None if missing else plan
    denied = HTTPException(status_code=403, detail="project access denied")

    with patch(
        "app.api.migration_plans.require_project_member",
        new=AsyncMock(side_effect=denied),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_migration_plan(
                migration_plan_uuid=plan.migration_plan_uuid,
                user=_user(),
                session=session,
            )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "migration plan not found"


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


def test_migration_plan_openapi_contract_uses_structured_models() -> None:
    schema = MigrationPlanOut.model_json_schema()

    for binding in (
        "project_space_uuid",
        "schema_model_revision_uuid",
        "db_connection_uuid",
        "base_schema_snapshot_uuid",
        "snapshot_contract_version",
        "postgresql_major",
        "created_by_user_uuid",
        "created_at",
    ):
        assert binding in schema["required"]

    assert schema["properties"]["statements"]["items"] == {
        "$ref": "#/$defs/MigrationPlanStatement"
    }
    assert schema["properties"]["blockers"]["items"] == {
        "$ref": "#/$defs/MigrationPlanBlocker"
    }
    assert schema["properties"]["risk_summary"] == {
        "$ref": "#/$defs/MigrationPlanRiskSummary"
    }


def test_migration_plan_preview_route_is_published_in_openapi() -> None:
    from app.main import app

    operation = app.openapi()["paths"][
        "/api/migration-plans/{migration_plan_uuid}"
    ]["get"]

    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/MigrationPlanOut"
    }


@pytest.mark.asyncio
async def test_create_migration_plan_reuses_unexpired_immutable_identity() -> None:
    inputs = _inputs()
    _, revision, connection, snapshot, _ = inputs
    compiled = compile_migration_plan(_model(), _model())
    existing = SimpleNamespace(
        migration_plan_uuid=uuid.uuid4(),
        project_space_uuid=inputs[0].project_space_uuid,
        schema_model_revision_uuid=revision.schema_model_revision_uuid,
        db_connection_uuid=connection.db_connection_uuid,
        base_schema_snapshot_uuid=snapshot.schema_snapshot_uuid,
        statement_digest=compiled["plan_digest"],
        base_digest=compiled["base_digest"],
        target_digest=compiled["target_digest"],
        compiler_version=compiled["compiler_version"],
        plan_json=compiled,
        created_by_user_uuid=uuid.uuid4(),
        created_at=dt.datetime.now(dt.timezone.utc),
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1),
    )
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
async def test_create_migration_plan_rejects_recently_expired_identity() -> None:
    """An expired identity remains a conflict until its retention window ends."""

    inputs = _inputs()
    _, revision, connection, snapshot, _ = inputs
    existing = _stored_plan()
    existing.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    session = FakeSession()

    with patch(
        "app.api.migration_plans._load_plan_inputs",
        new=AsyncMock(return_value=inputs),
    ), patch(
        "app.api.migration_plans.require_project_member", new_callable=AsyncMock
    ), patch(
        "app.api.migration_plans._existing_plan",
        new=AsyncMock(return_value=existing),
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

    assert exc_info.value.status_code == 409
    assert "expired" in exc_info.value.detail


@pytest.mark.asyncio
async def test_create_migration_plan_reuses_concurrent_insert_winner() -> None:
    """A losing concurrent insert rolls back and returns the immutable winner."""

    inputs = _inputs()
    _, revision, connection, snapshot, _ = inputs
    winner = _stored_plan()
    session = FakeSession()
    session.commit.side_effect = IntegrityError(
        "INSERT INTO migration_plan", {}, RuntimeError("duplicate key")
    )

    with patch(
        "app.api.migration_plans._load_plan_inputs",
        new=AsyncMock(return_value=inputs),
    ), patch(
        "app.api.migration_plans.require_project_member", new_callable=AsyncMock
    ), patch(
        "app.api.migration_plans._existing_plan",
        new=AsyncMock(side_effect=[None, winner]),
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

    assert out.migration_plan_uuid == winner.migration_plan_uuid
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_migration_plan_reraises_when_concurrent_winner_is_absent() -> None:
    """A uniqueness failure without a visible winner preserves the DB error."""

    inputs = _inputs()
    _, revision, connection, snapshot, _ = inputs
    session = FakeSession()
    error = IntegrityError(
        "INSERT INTO migration_plan", {}, RuntimeError("duplicate key")
    )
    session.commit.side_effect = error

    with patch(
        "app.api.migration_plans._load_plan_inputs",
        new=AsyncMock(return_value=inputs),
    ), patch(
        "app.api.migration_plans.require_project_member", new_callable=AsyncMock
    ), patch(
        "app.api.migration_plans._existing_plan",
        new=AsyncMock(side_effect=[None, None]),
    ):
        with pytest.raises(IntegrityError) as exc_info:
            await create_migration_plan(
                schema_model_revision_uuid=revision.schema_model_revision_uuid,
                body=MigrationPlanCreateIn(
                    db_connection_uuid=connection.db_connection_uuid,
                    base_schema_snapshot_uuid=snapshot.schema_snapshot_uuid,
                ),
                user=_user(),
                session=session,
            )

    assert exc_info.value is error
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_deletes_only_old_unreferenced_plans_in_one_project() -> None:
    """Retention cleanup is tenant-scoped and excludes plans with run history."""

    project_uuid = uuid.uuid4()
    now = dt.datetime(2026, 8, 11, tzinfo=dt.timezone.utc)
    session = FakeSession()
    session.execute.return_value = SimpleNamespace(rowcount=2)

    deleted = await _cleanup_expired_unreferenced_plans(
        session, project_space_uuid=project_uuid, now=now
    )

    statement = session.execute.await_args.args[0]
    compiled = statement.compile()
    assert project_uuid in compiled.params.values()
    assert now - EXPIRED_PLAN_RETENTION in compiled.params.values()
    assert "NOT (EXISTS" in str(compiled)
    assert deleted == 2
    session.commit.assert_awaited_once()

    session.execute.reset_mock()
    session.commit.reset_mock()
    session.execute.return_value = SimpleNamespace(rowcount=0)
    assert (
        await _cleanup_expired_unreferenced_plans(
            session, project_space_uuid=project_uuid, now=now
        )
        == 0
    )
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_index", range(5))
async def test_load_plan_inputs_returns_none_for_every_missing_resource(
    missing_index: int,
) -> None:
    """Every absent revision/model/connection/snapshot/data binding is masked."""

    revision_uuid = uuid.uuid4()
    body = MigrationPlanCreateIn(
        db_connection_uuid=uuid.uuid4(),
        base_schema_snapshot_uuid=uuid.uuid4(),
    )
    revision = SimpleNamespace(schema_model_uuid=uuid.uuid4())
    resources: list[object | None] = [
        revision,
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    ]
    resources[missing_index] = None
    session = FakeSession()
    session.get.side_effect = resources

    assert await _load_plan_inputs(session, revision_uuid, body) is None


@pytest.mark.asyncio
async def test_load_plan_inputs_returns_complete_binding() -> None:
    """A complete immutable input set is returned in authority order."""

    inputs = _inputs()
    _, revision, _, _, _ = inputs
    session = FakeSession()
    session.get.side_effect = [revision, inputs[0], *inputs[2:]]
    body = MigrationPlanCreateIn(
        db_connection_uuid=inputs[2].db_connection_uuid,
        base_schema_snapshot_uuid=inputs[3].schema_snapshot_uuid,
    )

    loaded = await _load_plan_inputs(
        session, revision.schema_model_revision_uuid, body
    )

    assert loaded == inputs


@pytest.mark.asyncio
async def test_get_migration_plan_preserves_non_authorization_http_error() -> None:
    """Only project denial is IDOR-masked; infrastructure HTTP errors survive."""

    plan = _stored_plan()
    session = FakeSession()
    session.get.return_value = plan
    upstream = HTTPException(status_code=503, detail="membership unavailable")

    with patch(
        "app.api.migration_plans.require_project_member",
        new=AsyncMock(side_effect=upstream),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_migration_plan(
                migration_plan_uuid=plan.migration_plan_uuid,
                user=_user(),
                session=session,
            )

    assert exc_info.value is upstream


@pytest.mark.asyncio
async def test_create_migration_plan_masks_missing_input() -> None:
    """A missing input set exposes no partial resource identity."""

    with patch(
        "app.api.migration_plans._load_plan_inputs",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await create_migration_plan(
                schema_model_revision_uuid=uuid.uuid4(),
                body=MigrationPlanCreateIn(
                    db_connection_uuid=uuid.uuid4(),
                    base_schema_snapshot_uuid=uuid.uuid4(),
                ),
                user=_user(),
                session=FakeSession(),
            )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_create_migration_plan_preserves_membership_service_error() -> None:
    """Non-denial membership errors are not mislabeled as missing inputs."""

    inputs = _inputs()
    upstream = HTTPException(status_code=503, detail="membership unavailable")
    with patch(
        "app.api.migration_plans._load_plan_inputs",
        new=AsyncMock(return_value=inputs),
    ), patch(
        "app.api.migration_plans.require_project_member",
        new=AsyncMock(side_effect=upstream),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await create_migration_plan(
                schema_model_revision_uuid=inputs[1].schema_model_revision_uuid,
                body=MigrationPlanCreateIn(
                    db_connection_uuid=inputs[2].db_connection_uuid,
                    base_schema_snapshot_uuid=inputs[3].schema_snapshot_uuid,
                ),
                user=_user(),
                session=FakeSession(),
            )

    assert exc_info.value is upstream


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "expected_detail"),
    [
        ("wrong_connection", "base snapshot was not captured"),
        ("snapshot_running", "base snapshot is not usable"),
        ("wrong_revision", "model revision binding is invalid"),
    ],
)
async def test_create_migration_plan_rejects_invalid_input_bindings(
    case: str,
    expected_detail: str,
) -> None:
    """Connection, snapshot status, and revision identity fail independently."""

    inputs = list(_inputs())
    if case == "wrong_connection":
        inputs[3].db_connection_uuid = uuid.uuid4()
    elif case == "snapshot_running":
        inputs[3].status = "running"
    else:
        inputs[1].schema_model_uuid = uuid.uuid4()

    with patch(
        "app.api.migration_plans._load_plan_inputs",
        new=AsyncMock(return_value=tuple(inputs)),
    ), patch(
        "app.api.migration_plans.require_project_member", new_callable=AsyncMock
    ):
        with pytest.raises(HTTPException) as exc_info:
            await create_migration_plan(
                schema_model_revision_uuid=inputs[1].schema_model_revision_uuid,
                body=MigrationPlanCreateIn(
                    db_connection_uuid=inputs[2].db_connection_uuid,
                    base_schema_snapshot_uuid=inputs[3].schema_snapshot_uuid,
                ),
                user=_user(),
                session=FakeSession(),
            )

    assert exc_info.value.status_code == 422
    assert expected_detail in exc_info.value.detail


@pytest.mark.asyncio
async def test_create_migration_plan_maps_compiler_validation_to_422() -> None:
    """Canonical snapshot/model validation errors remain non-executable input."""

    inputs = _inputs()
    with patch(
        "app.api.migration_plans._load_plan_inputs",
        new=AsyncMock(return_value=inputs),
    ), patch(
        "app.api.migration_plans.require_project_member", new_callable=AsyncMock
    ), patch(
        "app.api.migration_plans.anyio.to_thread.run_sync",
        new=AsyncMock(side_effect=SchemaModelValidationError("unsupported catalog")),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await create_migration_plan(
                schema_model_revision_uuid=inputs[1].schema_model_revision_uuid,
                body=MigrationPlanCreateIn(
                    db_connection_uuid=inputs[2].db_connection_uuid,
                    base_schema_snapshot_uuid=inputs[3].schema_snapshot_uuid,
                ),
                user=_user(),
                session=FakeSession(),
            )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "unsupported catalog"


@pytest.mark.asyncio
async def test_create_migration_plan_rejects_expired_concurrent_winner() -> None:
    """A concurrently selected expired winner never becomes a fresh preview."""

    inputs = _inputs()
    winner = _stored_plan()
    winner.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    session = FakeSession()
    session.commit.side_effect = IntegrityError(
        "INSERT INTO migration_plan", {}, RuntimeError("duplicate key")
    )
    with patch(
        "app.api.migration_plans._load_plan_inputs",
        new=AsyncMock(return_value=inputs),
    ), patch(
        "app.api.migration_plans.require_project_member", new_callable=AsyncMock
    ), patch(
        "app.api.migration_plans._existing_plan",
        new=AsyncMock(side_effect=[None, winner]),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await create_migration_plan(
                schema_model_revision_uuid=inputs[1].schema_model_revision_uuid,
                body=MigrationPlanCreateIn(
                    db_connection_uuid=inputs[2].db_connection_uuid,
                    base_schema_snapshot_uuid=inputs[3].schema_snapshot_uuid,
                ),
                user=_user(),
                session=session,
            )

    assert exc_info.value.status_code == 409
    session.rollback.assert_awaited_once()


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
