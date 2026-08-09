"""Read authorized, integrity-checked durable migration-run evidence."""

from __future__ import annotations

import uuid
from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.db import get_read_session
from app.forward.migration_run import (
    APPLY_RUN_STATES,
    DRY_RUN_STATES,
    MigrationRunContractError,
    canonicalize_run_evidence,
    digest_run_event,
    validate_run_transition,
)
from app.models import MigrationRun, MigrationRunEvent
from app.permissions import require_project_member
from app.schemas import MigrationRunEventOut, MigrationRunOut

router = APIRouter(prefix="/api/migration-runs", tags=["migration-runs"])
MAX_RETURNED_RUN_EVENTS = 1_000


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
                if event.state_before != event.state_after:
                    raise _integrity_error()
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
    if expected_state != run.state or previous_event_digest != run.latest_event_digest:
        raise _integrity_error()

    return MigrationRunOut(
        migration_run_uuid=run.migration_run_uuid,
        project_space_uuid=run.project_space_uuid,
        migration_plan_uuid=run.migration_plan_uuid,
        run_kind=cast(Literal["dry_run", "apply"], run.run_kind),
        state=run.state,
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
