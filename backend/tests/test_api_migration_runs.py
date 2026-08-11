from __future__ import annotations

import datetime as dt
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.migration_runs import (
    MAX_RETURNED_RUN_EVENTS,
    _request_id,
    cancel_migration_run,
    get_migration_run,
)
from app.auth import CurrentUser
from app.forward.migration_run import (
    MigrationRunCancellation,
    MigrationRunContractError,
    digest_run_event,
)
from app.models import MigrationRun, MigrationRunEvent
from app.schemas import MigrationRunCancelIn, MigrationRunOut


def _user() -> CurrentUser:
    return CurrentUser(uuid.uuid4(), "reviewer", "Reviewer")


def _request(request_id: str = "migration-request-123") -> Request:
    """Build an HTTP request carrying the middleware-selected correlation ID."""

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "https",
            "path": "/api/migration-runs/run/cancel",
            "raw_path": b"/api/migration-runs/run/cancel",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 443),
            "root_path": "",
            "http_version": "1.1",
        }
    )
    request.state.request_id = request_id
    return request


def test_request_id_uses_safe_fallback_without_observability_middleware() -> None:
    """A directly mounted router still produces a bounded correlation identity."""

    expected = uuid.uuid4()
    request = _request()
    del request.scope["state"]["request_id"]
    with patch("app.api.migration_runs.uuid.uuid4", return_value=expected):
        assert _request_id(request) == str(expected)


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
        latest_event_digest="d" * 64,
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
    events = [
        MigrationRunEvent(
            migration_run_event_uuid=uuid.uuid4(),
            migration_run_uuid=run.migration_run_uuid,
            sequence_number=1,
            event_type="run_queued",
            state_before=None,
            state_after="queued",
            evidence_json={"request_source": "review_ui"},
            previous_event_digest=None,
            event_digest="",
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
            previous_event_digest="",
            event_digest="",
            actor_user_uuid=None,
            created_at=run.updated_at,
        ),
    ]
    previous_digest = None
    for event in events:
        event.previous_event_digest = previous_digest
        event.event_digest = digest_run_event(
            migration_run_uuid=event.migration_run_uuid,
            sequence_number=event.sequence_number,
            event_type=event.event_type,
            state_before=event.state_before,
            state_after=event.state_after,
            evidence=event.evidence_json,
            actor_user_uuid=event.actor_user_uuid,
            created_at=event.created_at,
            previous_event_digest=previous_digest,
        )
        previous_digest = event.event_digest
    run.latest_event_digest = events[-1].event_digest
    return events


def _event_digest(event: MigrationRunEvent) -> str:
    """Recompute one fixture event after an intentional test mutation."""

    return digest_run_event(
        migration_run_uuid=event.migration_run_uuid,
        sequence_number=event.sequence_number,
        event_type=event.event_type,
        state_before=event.state_before,
        state_after=event.state_after,
        evidence=event.evidence_json,
        actor_user_uuid=event.actor_user_uuid,
        created_at=event.created_at,
        previous_event_digest=event.previous_event_digest,
    )


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
    assert out.events[-1].previous_event_digest == out.events[0].event_digest
    assert out.events[-1].event_digest == run.latest_event_digest
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
async def test_cancel_migration_run_persists_correlated_editor_intent() -> None:
    """An editor gets one accepted resource after the CAS event commits."""

    run = _run()
    session = SimpleNamespace(
        get=AsyncMock(return_value=run),
        commit=AsyncMock(),
    )
    cancellation = MigrationRunCancellation(
        state=run.state,
        state_version=run.state_version + 1,
        reused=False,
    )
    with (
        patch(
            "app.api.migration_runs.require_project_member",
            new_callable=AsyncMock,
        ) as membership,
        patch(
            "app.api.migration_runs.request_migration_run_cancellation",
            new=AsyncMock(return_value=cancellation),
        ) as writer,
    ):
        out = await cancel_migration_run(
            migration_run_uuid=run.migration_run_uuid,
            body=MigrationRunCancelIn(expected_state_version=run.state_version),
            request=_request(),
            user=_user(),
            session=session,
        )

    assert out.migration_run_uuid == run.migration_run_uuid
    assert out.state == run.state
    assert out.state_version == run.state_version + 1
    assert out.cancellation_requested is True
    assert out.reused is False
    membership.assert_awaited_once()
    assert membership.await_args.kwargs["minimum_role"] == "editor"
    assert writer.await_args.kwargs["evidence"] == {
        "request_id": "migration-request-123",
        "request_source": "api",
    }
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message", "code"),
    [
        ("migration run state version conflict", "stale_run"),
        ("terminal migration run cannot be cancelled", "run_not_cancellable"),
        ("migration run state is invalid", "run_integrity_invalid"),
        ("run evidence is too large", "run_action_rejected"),
    ],
)
async def test_cancel_migration_run_maps_contract_errors_without_leaking(
    message: str, code: str
) -> None:
    """Cancellation failures expose stable codes instead of internal details."""

    run = _run()
    session = SimpleNamespace(
        get=AsyncMock(return_value=run),
        commit=AsyncMock(),
    )
    with (
        patch(
            "app.api.migration_runs.require_project_member",
            new_callable=AsyncMock,
        ),
        patch(
            "app.api.migration_runs.request_migration_run_cancellation",
            new=AsyncMock(side_effect=MigrationRunContractError(message)),
        ),
        pytest.raises(HTTPException) as exc_info,
    ):
        await cancel_migration_run(
            migration_run_uuid=run.migration_run_uuid,
            body=MigrationRunCancelIn(expected_state_version=run.state_version),
            request=_request("safe-correlation"),
            user=_user(),
            session=session,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == {
        "code": code,
        "detail": "migration run cancellation was rejected",
        "correlation_id": "safe-correlation",
    }
    assert message not in str(exc_info.value.detail)
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("membership_error", "status", "code"),
    [
        ("project access denied", 404, "migration_run_not_found"),
        ("insufficient project role", 403, "run_role_required"),
    ],
)
async def test_cancel_migration_run_masks_nonmembers_but_rejects_viewers(
    membership_error: str, status: int, code: str
) -> None:
    """Cross-project identities stay hidden while viewers get a role error."""

    run = _run()
    session = SimpleNamespace(
        get=AsyncMock(return_value=run),
        commit=AsyncMock(),
    )
    with (
        patch(
            "app.api.migration_runs.require_project_member",
            new=AsyncMock(
                side_effect=HTTPException(status_code=403, detail=membership_error)
            ),
        ),
        patch(
            "app.api.migration_runs.request_migration_run_cancellation",
            new_callable=AsyncMock,
        ) as writer,
        pytest.raises(HTTPException) as exc_info,
    ):
        await cancel_migration_run(
            migration_run_uuid=run.migration_run_uuid,
            body=MigrationRunCancelIn(expected_state_version=run.state_version),
            request=_request(),
            user=_user(),
            session=session,
        )

    assert exc_info.value.status_code == status
    assert exc_info.value.detail["code"] == code
    writer.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancel_migration_run_preserves_unexpected_authorization_errors() -> None:
    """Only expected membership denials are converted into public action errors."""

    run = _run()
    session = SimpleNamespace(
        get=AsyncMock(return_value=run),
        commit=AsyncMock(),
    )
    with (
        patch(
            "app.api.migration_runs.require_project_member",
            new=AsyncMock(side_effect=HTTPException(status_code=503, detail="busy")),
        ),
        pytest.raises(HTTPException) as exc_info,
    ):
        await cancel_migration_run(
            migration_run_uuid=run.migration_run_uuid,
            body=MigrationRunCancelIn(expected_state_version=run.state_version),
            request=_request(),
            user=_user(),
            session=session,
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "busy"
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancel_migration_run_masks_missing_identity() -> None:
    """An unknown run returns the same structured identity error as a nonmember."""

    session = SimpleNamespace(
        get=AsyncMock(return_value=None),
        commit=AsyncMock(),
    )
    with pytest.raises(HTTPException) as exc_info:
        await cancel_migration_run(
            migration_run_uuid=uuid.uuid4(),
            body=MigrationRunCancelIn(expected_state_version=1),
            request=_request(),
            user=_user(),
            session=session,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "migration_run_not_found"
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        "gap",
        "chain",
        "secret",
        "state",
        "time",
        "final",
        "digest",
        "predecessor",
        "anchor",
        "graph",
        "genesis",
        "cancellation_graph",
        "missing_before",
        "cancellation_flag",
    ],
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
    elif mutation == "state":
        run.run_kind = "preview"
    elif mutation == "time":
        events[1].created_at = run.created_at - dt.timedelta(seconds=1)
    elif mutation == "final":
        events[1].state_after = "live_preflight_running"
    elif mutation == "digest":
        events[1].event_digest = "f" * 64
    elif mutation == "predecessor":
        events[1].previous_event_digest = "f" * 64
    elif mutation == "graph":
        events[1].state_after = "passed"
        events[1].event_digest = digest_run_event(
            migration_run_uuid=events[1].migration_run_uuid,
            sequence_number=events[1].sequence_number,
            event_type=events[1].event_type,
            state_before=events[1].state_before,
            state_after=events[1].state_after,
            evidence=events[1].evidence_json,
            actor_user_uuid=events[1].actor_user_uuid,
            created_at=events[1].created_at,
            previous_event_digest=events[1].previous_event_digest,
        )
        run.state = "passed"
        run.latest_event_digest = events[1].event_digest
    elif mutation == "genesis":
        events[0].event_type = "unexpected_genesis"
        events[0].event_digest = _event_digest(events[0])
        events[1].previous_event_digest = events[0].event_digest
        events[1].event_digest = _event_digest(events[1])
        run.latest_event_digest = events[1].event_digest
    elif mutation == "cancellation_graph":
        events[1].event_type = "cancellation_requested"
        events[1].event_digest = _event_digest(events[1])
        run.latest_event_digest = events[1].event_digest
    elif mutation == "missing_before":
        events[1].state_before = None
        events[1].event_digest = _event_digest(events[1])
        run.latest_event_digest = events[1].event_digest
    elif mutation == "cancellation_flag":
        run.cancellation_requested = True
    else:
        run.latest_event_digest = "f" * 64
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
async def test_get_migration_run_rejects_a_sequential_chain_over_event_limit() -> None:
    """The size guard rejects a sequential digest chain before replay work."""

    run = _run()
    events = _events(run)[:1]
    previous_digest = events[0].event_digest
    for sequence_number in range(2, MAX_RETURNED_RUN_EVENTS + 2):
        event = MigrationRunEvent(
            migration_run_event_uuid=uuid.uuid4(),
            migration_run_uuid=run.migration_run_uuid,
            sequence_number=sequence_number,
            event_type="evidence_recorded",
            state_before="queued",
            state_after="queued",
            evidence_json={"record": sequence_number},
            previous_event_digest=previous_digest,
            event_digest="",
            actor_user_uuid=None,
            created_at=run.created_at + dt.timedelta(microseconds=sequence_number),
        )
        event.event_digest = _event_digest(event)
        previous_digest = event.event_digest
        events.append(event)
    run.state = "queued"
    run.state_version = len(events)
    run.latest_event_digest = previous_digest
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

    assert len(events) == MAX_RETURNED_RUN_EVENTS + 1
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "migration run integrity verification failed"


def test_migration_run_openapi_state_matches_database_contract() -> None:
    """The public run state enum exposes every and only persisted state token."""

    state_schema = MigrationRunOut.model_json_schema()["properties"]["state"]
    assert set(state_schema["enum"]) == {
        "queued",
        "sandbox_running",
        "live_preflight_running",
        "passed",
        "drifted",
        "failed",
        "applying",
        "reconciling",
        "verifying",
        "verified",
        "drifted_no_apply",
        "not_applied",
        "verification_failed",
        "failed_rolled_back",
        "applied_with_drift",
        "outcome_unknown",
    }


@pytest.mark.asyncio
async def test_get_migration_run_supports_valid_apply_history() -> None:
    """The same bounded polling contract represents an apply state graph."""

    run = _run()
    run.run_kind = "apply"
    run.state = "applying"
    events = _events(run)
    events[1].event_type = "apply_started"
    events[1].state_after = "applying"
    events[1].event_digest = digest_run_event(
        migration_run_uuid=events[1].migration_run_uuid,
        sequence_number=events[1].sequence_number,
        event_type=events[1].event_type,
        state_before=events[1].state_before,
        state_after=events[1].state_after,
        evidence=events[1].evidence_json,
        actor_user_uuid=events[1].actor_user_uuid,
        created_at=events[1].created_at,
        previous_event_digest=events[1].previous_event_digest,
    )
    run.latest_event_digest = events[1].event_digest
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
async def test_get_migration_run_supports_valid_same_state_cancellation() -> None:
    """Cancellation evidence advances the version without inventing a state."""

    run = _run()
    events = _events(run)
    event = MigrationRunEvent(
        migration_run_event_uuid=uuid.uuid4(),
        migration_run_uuid=run.migration_run_uuid,
        sequence_number=3,
        event_type="cancellation_requested",
        state_before="sandbox_running",
        state_after="sandbox_running",
        evidence_json={"request_source": "review_ui"},
        previous_event_digest=events[-1].event_digest,
        event_digest="",
        actor_user_uuid=run.requested_by_user_uuid,
        created_at=run.updated_at + dt.timedelta(seconds=1),
    )
    event.event_digest = digest_run_event(
        migration_run_uuid=event.migration_run_uuid,
        sequence_number=event.sequence_number,
        event_type=event.event_type,
        state_before=event.state_before,
        state_after=event.state_after,
        evidence=event.evidence_json,
        actor_user_uuid=event.actor_user_uuid,
        created_at=event.created_at,
        previous_event_digest=event.previous_event_digest,
    )
    events.append(event)
    run.state_version = 3
    run.latest_event_digest = event.event_digest
    run.cancellation_requested = True
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

    assert out.state == "sandbox_running"
    assert out.state_version == 3
    assert out.cancellation_requested is True
    assert out.events[-1].event_type == "cancellation_requested"


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
