"""Read and cancel authorized, integrity-checked durable migration runs."""

from __future__ import annotations

import uuid
from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.db import get_read_session, get_session
from app.forward.migration_run import (
    APPLY_RUN_STATES,
    DRY_RUN_STATES,
    MigrationRunContractError,
    canonicalize_run_evidence,
    digest_run_event,
    request_migration_run_cancellation,
    validate_run_transition,
)
from app.models import MigrationRun, MigrationRunEvent
from app.permissions import require_project_member
from app.schemas import (
    MigrationRunActionOut,
    MigrationRunCancelIn,
    MigrationRunEventOut,
    MigrationRunOut,
    MigrationRunState,
)

router = APIRouter(prefix="/api/migration-runs", tags=["migration-runs"])
MAX_RETURNED_RUN_EVENTS = 1_000


def _request_id(request: Request) -> str:
    """Return the middleware-selected request ID or a safe local fallback."""

    value = getattr(request.state, "request_id", None)
    if isinstance(value, str) and 1 <= len(value) <= 64:
        return value
    return str(uuid.uuid4())


def _action_error(
    request: Request,
    *,
    status_code: int,
    code: str,
    detail: str,
) -> HTTPException:
    """Return the stable sanitized error envelope for mutating run APIs."""

    return HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "detail": detail,
            "correlation_id": _request_id(request),
        },
    )


def _cancellation_contract_error(
    request: Request, error: MigrationRunContractError
) -> HTTPException:
    """Map internal cancellation failures onto bounded public error codes."""

    message = str(error)
    code = {
        "migration run state version conflict": "stale_run",
        "terminal migration run cannot be cancelled": "run_not_cancellable",
        "migration run state is invalid": "run_integrity_invalid",
    }.get(message, "run_action_rejected")
    return _action_error(
        request,
        status_code=status.HTTP_409_CONFLICT,
        code=code,
        detail="migration run cancellation was rejected",
    )


def _integrity_error() -> HTTPException:
    """Return one sanitized response for every corrupt durable-history shape."""

    return HTTPException(
        status_code=409,
        detail="migration run integrity verification failed",
    )


def _run_out(
    run: MigrationRun, events: list[MigrationRunEvent]
) -> MigrationRunOut:
    """Verify sequence/state/evidence integrity before constructing output."""

    if len(events) > MAX_RETURNED_RUN_EVENTS or len(events) != run.state_version:
        raise _integrity_error()
    if run.run_kind not in {"dry_run", "apply"} or run.state not in (
        DRY_RUN_STATES if run.run_kind == "dry_run" else APPLY_RUN_STATES
    ):
        raise _integrity_error()
    expected_state: str | None = None
    previous_created_at = None
    previous_event_digest = None
    cancellation_event_seen = False
    event_output: list[MigrationRunEventOut] = []
    try:
        run_evidence = canonicalize_run_evidence(run.evidence_json)
        for expected_sequence, event in enumerate(events, start=1):
            canonical_evidence = canonicalize_run_evidence(event.evidence_json)
            if expected_sequence == 1:
                if (
                    event.event_type != "run_queued"
                    or event.state_before is not None
                    or event.state_after != "queued"
                ):
                    raise _integrity_error()
            elif event.event_type == "cancellation_requested":
                if cancellation_event_seen or event.state_before != event.state_after:
                    raise _integrity_error()
                cancellation_event_seen = True
            else:
                if event.state_before is None:
                    raise _integrity_error()
                validate_run_transition(
                    run.run_kind, event.state_before, event.state_after
                )
            if (
                event.sequence_number != expected_sequence
                or event.state_before != expected_state
                or event.previous_event_digest != previous_event_digest
                or event.event_digest
                != digest_run_event(
                    migration_run_uuid=event.migration_run_uuid,
                    sequence_number=event.sequence_number,
                    event_type=event.event_type,
                    state_before=event.state_before,
                    state_after=event.state_after,
                    evidence=canonical_evidence,
                    actor_user_uuid=event.actor_user_uuid,
                    created_at=event.created_at,
                    previous_event_digest=event.previous_event_digest,
                )
                or (
                    previous_created_at is not None
                    and event.created_at < previous_created_at
                )
            ):
                raise _integrity_error()
            event_output.append(
                MigrationRunEventOut(
                    sequence_number=event.sequence_number,
                    event_type=event.event_type,
                    state_before=event.state_before,
                    state_after=event.state_after,
                    evidence=canonical_evidence,
                    previous_event_digest=event.previous_event_digest,
                    event_digest=event.event_digest,
                    actor_user_uuid=event.actor_user_uuid,
                    created_at=event.created_at,
                )
            )
            expected_state = event.state_after
            previous_created_at = event.created_at
            previous_event_digest = event.event_digest
    except MigrationRunContractError as exc:
        raise _integrity_error() from exc
    if (
        expected_state != run.state
        or previous_event_digest != run.latest_event_digest
        or cancellation_event_seen != run.cancellation_requested
    ):
        raise _integrity_error()

    return MigrationRunOut(
        migration_run_uuid=run.migration_run_uuid,
        project_space_uuid=run.project_space_uuid,
        migration_plan_uuid=run.migration_plan_uuid,
        run_kind=cast(Literal["dry_run", "apply"], run.run_kind),
        state=cast(MigrationRunState, run.state),
        state_version=run.state_version,
        plan_digest=run.plan_digest,
        requested_by_user_uuid=run.requested_by_user_uuid,
        cancellation_requested=run.cancellation_requested,
        observed_base_digest=run.observed_base_digest,
        evidence=run_evidence,
        error_code=run.error_code,
        created_at=run.created_at,
        updated_at=run.updated_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        events=event_output,
    )


@router.post(
    "/{migration_run_uuid}/cancel",
    response_model=MigrationRunActionOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def cancel_migration_run(
    migration_run_uuid: uuid.UUID,
    body: MigrationRunCancelIn,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MigrationRunActionOut:
    """Persist one editor-authorized cancellation intent and audit event."""

    run = await session.get(MigrationRun, migration_run_uuid)
    if run is None:
        raise _action_error(
            request,
            status_code=status.HTTP_404_NOT_FOUND,
            code="migration_run_not_found",
            detail="migration run not found",
        )
    try:
        await require_project_member(
            session,
            run.project_space_uuid,
            user.user_account_uuid,
            minimum_role="editor",
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_403_FORBIDDEN:
            if exc.detail == "insufficient project role":
                raise _action_error(
                    request,
                    status_code=status.HTTP_403_FORBIDDEN,
                    code="run_role_required",
                    detail="editor role required",
                ) from exc
            raise _action_error(
                request,
                status_code=status.HTTP_404_NOT_FOUND,
                code="migration_run_not_found",
                detail="migration run not found",
            ) from exc
        raise

    correlation_id = _request_id(request)
    try:
        cancellation = await request_migration_run_cancellation(
            session,
            migration_run_uuid=migration_run_uuid,
            expected_state_version=body.expected_state_version,
            actor_user_uuid=user.user_account_uuid,
            evidence={
                "request_id": correlation_id,
                "request_source": "api",
            },
        )
    except MigrationRunContractError as exc:
        raise _cancellation_contract_error(request, exc) from exc
    await session.commit()
    return MigrationRunActionOut(
        migration_run_uuid=migration_run_uuid,
        state=cast(MigrationRunState, cancellation.state),
        state_version=cancellation.state_version,
        cancellation_requested=True,
        reused=cancellation.reused,
    )


@router.get("/{migration_run_uuid}", response_model=MigrationRunOut)
async def get_migration_run(
    migration_run_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> MigrationRunOut:
    """Return one project-authorized run with bounded verified evidence."""

    run = await session.get(MigrationRun, migration_run_uuid)
    if run is None:
        raise HTTPException(status_code=404, detail="migration run not found")
    try:
        await require_project_member(
            session,
            run.project_space_uuid,
            user.user_account_uuid,
        )
    except HTTPException as exc:
        if exc.status_code == 403:
            raise HTTPException(
                status_code=404, detail="migration run not found"
            ) from exc
        raise

    events = list(
        (
            await session.scalars(
                select(MigrationRunEvent)
                .where(MigrationRunEvent.migration_run_uuid == migration_run_uuid)
                .order_by(MigrationRunEvent.sequence_number)
                .limit(MAX_RETURNED_RUN_EVENTS + 1)
            )
        ).all()
    )
    return _run_out(run, events)
