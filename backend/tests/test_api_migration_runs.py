from __future__ import annotations

import datetime as dt
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.api.migration_runs import get_migration_run
from app.auth import CurrentUser
from app.models import MigrationRun, MigrationRunEvent


def _user() -> CurrentUser:
    return CurrentUser(uuid.uuid4(), "reviewer", "Reviewer")


def _run() -> MigrationRun:
    return MigrationRun(
        migration_run_uuid=uuid.uuid4(),
        project_space_uuid=uuid.uuid4(),
        migration_plan_uuid=uuid.uuid4(),
        run_kind="dry_run",
        state="sandbox_running",
        state_version=2,
        idempotency_key_hash="a" * 64,
        plan_digest="b" * 64,
        request_digest="c" * 64,
        requested_by_user_uuid=uuid.uuid4(),
        cancellation_requested=False,
        observed_base_digest=None,
        evidence_json={"sandbox_version": "postgresql-18"},
        error_code=None,
        created_at=dt.datetime(2026, 8, 10, tzinfo=dt.timezone.utc),
        updated_at=dt.datetime(2026, 8, 10, 0, 1, tzinfo=dt.timezone.utc),
        started_at=dt.datetime(2026, 8, 10, 0, 1, tzinfo=dt.timezone.utc),
        finished_at=None,
    )


def _events(run: MigrationRun) -> list[MigrationRunEvent]:
    return [
        MigrationRunEvent(
            migration_run_event_uuid=uuid.uuid4(),
            migration_run_uuid=run.migration_run_uuid,
            sequence_number=1,
            event_type="run_queued",
            state_before=None,
            state_after="queued",
            evidence_json={"request_source": "review_ui"},
            actor_user_uuid=run.requested_by_user_uuid,
            created_at=run.created_at,
        ),
        MigrationRunEvent(
            migration_run_event_uuid=uuid.uuid4(),
            migration_run_uuid=run.migration_run_uuid,
            sequence_number=2,
            event_type="sandbox_started",
            state_before="queued",
            state_after="sandbox_running",
            evidence_json={"sandbox_version": "postgresql-18"},
            actor_user_uuid=None,
            created_at=run.updated_at,
        ),
    ]


@pytest.mark.asyncio
async def test_get_migration_run_returns_bounded_authorized_history() -> None:
    """A member can poll exact state identity and sanitized ordered evidence."""

    run = _run()
    events = _events(run)
    session = SimpleNamespace(
        get=AsyncMock(return_value=run),
        scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: events)),
    )
    with patch(
        "app.api.migration_runs.require_project_member", new_callable=AsyncMock
    ) as membership:
        out = await get_migration_run(
            migration_run_uuid=run.migration_run_uuid,
            user=_user(),
            session=session,
        )

    assert out.migration_run_uuid == run.migration_run_uuid
    assert out.migration_plan_uuid == run.migration_plan_uuid
    assert out.state == "sandbox_running"
    assert out.state_version == 2
    assert [event.sequence_number for event in out.events] == [1, 2]
    assert out.events[-1].evidence == {"sandbox_version": "postgresql-18"}
    membership.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_migration_run_masks_non_member_as_not_found() -> None:
    """A run UUID cannot disclose a project to a non-member."""

    run = _run()
    session = SimpleNamespace(get=AsyncMock(return_value=run), scalars=AsyncMock())
    with patch(
        "app.api.migration_runs.require_project_member",
        new=AsyncMock(side_effect=HTTPException(status_code=403, detail="denied")),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_migration_run(
                migration_run_uuid=run.migration_run_uuid,
                user=_user(),
                session=session,
            )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "migration run not found"
    session.scalars.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation", ["gap", "chain", "secret", "overflow", "state", "time", "final"]
)
async def test_get_migration_run_fails_closed_for_corrupt_history(
    mutation: str,
) -> None:
    """Sequence, chain, evidence, and size corruption never reaches a client."""

    run = _run()
    events = _events(run)
    if mutation == "gap":
        events[1].sequence_number = 3
    elif mutation == "chain":
        events[1].state_before = "live_preflight_running"
    elif mutation == "secret":
        events[1].evidence_json = {"databaseDsn": "postgresql://secret"}
    elif mutation == "overflow":
        events = events * 501
    elif mutation == "state":
        run.run_kind = "preview"
    elif mutation == "time":
        events[1].created_at = run.created_at - dt.timedelta(seconds=1)
    else:
        events[1].state_after = "live_preflight_running"
    session = SimpleNamespace(
        get=AsyncMock(return_value=run),
        scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: events)),
    )
    with patch(
        "app.api.migration_runs.require_project_member", new_callable=AsyncMock
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_migration_run(
                migration_run_uuid=run.migration_run_uuid,
                user=_user(),
                session=session,
            )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "migration run integrity verification failed"


@pytest.mark.asyncio
async def test_get_migration_run_supports_valid_apply_history() -> None:
    """The same bounded polling contract represents an apply state graph."""

    run = _run()
    run.run_kind = "apply"
    run.state = "applying"
    events = _events(run)
    events[1].event_type = "apply_started"
    events[1].state_after = "applying"
    session = SimpleNamespace(
        get=AsyncMock(return_value=run),
        scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: events)),
    )
    with patch(
        "app.api.migration_runs.require_project_member", new_callable=AsyncMock
    ):
        out = await get_migration_run(
            migration_run_uuid=run.migration_run_uuid,
            user=_user(),
            session=session,
        )

    assert out.run_kind == "apply"
    assert out.state == "applying"


@pytest.mark.asyncio
async def test_get_migration_run_handles_missing_and_non_membership_http_errors() -> None:
    """Missing rows are masked while non-membership HTTP failures propagate."""

    session = SimpleNamespace(get=AsyncMock(return_value=None), scalars=AsyncMock())
    with pytest.raises(HTTPException) as missing:
        await get_migration_run(
            migration_run_uuid=uuid.uuid4(), user=_user(), session=session
        )
    assert missing.value.status_code == 404

    run = _run()
    session.get.return_value = run
    with patch(
        "app.api.migration_runs.require_project_member",
        new=AsyncMock(side_effect=HTTPException(status_code=503, detail="unavailable")),
    ):
        with pytest.raises(HTTPException) as unavailable:
            await get_migration_run(
                migration_run_uuid=run.migration_run_uuid,
                user=_user(),
                session=session,
            )
    assert unavailable.value.status_code == 503
    session.scalars.assert_not_awaited()
