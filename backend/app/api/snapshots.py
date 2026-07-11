from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.db import get_read_session, get_session
from app.models import (
    DbConnection,
    JobQueue,
    SchemaSnapshot,
    SchemaSnapshotData,
    TableAnnotation,
)
from app.permissions import require_project_member
from app.schemas import (
    FkCyclesOut,
    IndexRedundancyOut,
    InferredRelationshipOut,
    MigrationSafetyOut,
    NamingLintOut,
    SchemaStatsOut,
    SensitiveColumnsOut,
    SnapshotCreateIn,
    SnapshotDetailOut,
    SnapshotDiffOut,
    SnapshotOut,
    WideTablesOut,
)
from app.ddl.export import snapshot_json_to_sql
from app.ddl.migration import snapshot_diff_to_migration_sql
from app.ddl.migration_safety import analyze_migration_safety
from app.diff.schema_diff import diff_snapshots
from app.spec.fk_cycles import detect_fk_cycles
from app.spec.index_redundancy import detect_index_redundancy
from app.spec.data_dictionary import snapshot_to_data_dictionary_md
from app.spec.naming_lint import lint_naming
from app.spec.relationship_inference import infer_relationships
from app.spec.schema_stats import compute_schema_stats
from app.spec.sensitive_columns import detect_sensitive_columns
from app.spec.wide_tables import detect_wide_tables
from app.jobs.valkey_queue import enqueue_job_signal
from app.spec.llm import (
    LlmConfigurationError,
    LlmProviderError,
    generate_index_design_llm_draft,
    generate_reversing_llm_draft,
)
from app.spec.index_design import generate_index_design_spec
from app.spec.reversing import generate_reversing_spec

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])


def _snapshot_not_found(schema_snapshot_uuid: uuid.UUID) -> SnapshotDetailOut:
    """Return the uniform snapshot-not-found response."""

    return SnapshotDetailOut(
        schema_snapshot_uuid=schema_snapshot_uuid,
        status="not_found",
        schema_filter=None,
        error_message="snapshot not found",
        snapshot_json=None,
    )


async def _get_authorized_snapshot(
    session: AsyncSession,
    schema_snapshot_uuid: uuid.UUID,
    user: CurrentUser,
) -> SchemaSnapshot | None:
    """Fetch a snapshot only after project membership has been checked.

    A missing snapshot and a snapshot in another project both return ``None`` so
    UUID-based read endpoints cannot be used to enumerate snapshot existence.
    """

    project_space_uuid = await session.scalar(
        select(SchemaSnapshot.project_space_uuid).where(
            SchemaSnapshot.schema_snapshot_uuid == schema_snapshot_uuid
        )
    )
    if project_space_uuid is None:
        return None

    try:
        await require_project_member(
            session, project_space_uuid, user.user_account_uuid
        )
    except HTTPException as exc:
        if exc.status_code == 403:
            return None
        raise

    return await session.get(SchemaSnapshot, schema_snapshot_uuid)


@router.post("/by-project/{project_space_uuid}", response_model=SnapshotOut)
async def create_snapshot(
    project_space_uuid: uuid.UUID,
    body: SnapshotCreateIn,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> SnapshotOut:
    """Create a schema snapshot job for a project connection."""
    await require_project_member(
        session, project_space_uuid, user.user_account_uuid, minimum_role="editor"
    )

    # Ensure connection belongs to this project
    conn = await session.get(DbConnection, body.db_connection_uuid)
    if conn is None or conn.project_space_uuid != project_space_uuid:
        raise HTTPException(status_code=404, detail="connection not found")

    snap = SchemaSnapshot(
        schema_snapshot_uuid=uuid.uuid4(),
        project_space_uuid=project_space_uuid,
        db_connection_uuid=body.db_connection_uuid,
        status="queued",
        schema_filter=body.schema_filter,
        started_at=None,
        finished_at=None,
        error_message=None,
        created_at=dt.datetime.now(dt.timezone.utc),
    )
    session.add(snap)

    job = JobQueue(
        job_queue_uuid=uuid.uuid4(),
        job_type="snapshot",
        status="queued",
        payload_json={"schema_snapshot_uuid": str(snap.schema_snapshot_uuid)},
        run_after=dt.datetime.now(dt.timezone.utc),
        attempt_count=0,
        last_error=None,
        created_at=dt.datetime.now(dt.timezone.utc),
        started_at=None,
        finished_at=None,
    )
    session.add(job)

    await session.commit()
    await enqueue_job_signal(job.job_queue_uuid, job.run_after)
    return SnapshotOut(
        schema_snapshot_uuid=snap.schema_snapshot_uuid,
        status=snap.status,
        schema_filter=snap.schema_filter,
    )


@router.get("/{schema_snapshot_uuid}", response_model=SnapshotDetailOut)
async def get_snapshot(
    schema_snapshot_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> SnapshotDetailOut:
    """Get a project-authorized snapshot status and captured JSON.

    The snapshot payload is loaded only after ``_get_authorized_snapshot`` has
    verified project membership. Missing and unauthorized snapshots share the
    same not-found response.
    """
    snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    if snap is None:
        return _snapshot_not_found(schema_snapshot_uuid)
    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    return SnapshotDetailOut(
        schema_snapshot_uuid=snap.schema_snapshot_uuid,
        status=snap.status,
        schema_filter=snap.schema_filter,
        error_message=snap.error_message,
        snapshot_json=data.snapshot_json if data else None,
    )


@router.get(
    "/{schema_snapshot_uuid}/inferred-relationships",
    response_model=list[InferredRelationshipOut],
)
async def inferred_relationships(
    schema_snapshot_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> list[InferredRelationshipOut]:
    """Suggest implicit (undeclared) foreign keys inferred from naming.

    Useful for reverse-engineering databases that never declared their FKs.
    Returns an empty list for missing/unauthorized snapshots (uniform response).
    """
    snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    if snap is None:
        return []
    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    if data is None:
        return []
    return [
        InferredRelationshipOut(**rel)
        for rel in infer_relationships(data.snapshot_json)
    ]


@router.get("/{schema_snapshot_uuid}/diff", response_model=SnapshotDiffOut)
async def diff_snapshot(
    schema_snapshot_uuid: uuid.UUID,
    against: uuid.UUID = Query(
        ..., description="Base snapshot UUID to compare this snapshot against"
    ),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> SnapshotDiffOut:
    """Diff this snapshot (target) against another (base).

    Both snapshots are authorized independently via project membership, so a
    caller can only diff snapshots they may already read. If either is missing
    or unauthorized, a uniform ``not_found`` response is returned so existence
    cannot be enumerated.
    """
    target_snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    base_snap = await _get_authorized_snapshot(session, against, user)
    if target_snap is None or base_snap is None:
        return SnapshotDiffOut(
            base_snapshot_uuid=against,
            target_snapshot_uuid=schema_snapshot_uuid,
            status="not_found",
            diff=None,
        )
    base_data = await session.get(SchemaSnapshotData, against)
    target_data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    diff = diff_snapshots(
        base_data.snapshot_json if base_data else None,
        target_data.snapshot_json if target_data else None,
    )
    return SnapshotDiffOut(
        base_snapshot_uuid=against,
        target_snapshot_uuid=schema_snapshot_uuid,
        status="ok",
        diff=diff,
    )


@router.get(
    "/{schema_snapshot_uuid}/migration-safety", response_model=MigrationSafetyOut
)
async def migration_safety(
    schema_snapshot_uuid: uuid.UUID,
    against: uuid.UUID = Query(
        ..., description="Base snapshot UUID to analyze migrating from"
    ),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> MigrationSafetyOut:
    """Risk-classify the migration from the base snapshot to this one.

    Each change is labelled safe / warning / destructive with an explanation so
    a reviewer can spot data loss and table-locking operations before applying.
    Both snapshots are authorized independently (uniform not-found).
    """
    target_snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    base_snap = await _get_authorized_snapshot(session, against, user)
    if target_snap is None or base_snap is None:
        return MigrationSafetyOut(
            base_snapshot_uuid=against,
            target_snapshot_uuid=schema_snapshot_uuid,
            status="not_found",
            analysis=None,
        )
    base_data = await session.get(SchemaSnapshotData, against)
    target_data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    analysis = analyze_migration_safety(
        base_data.snapshot_json if base_data else None,
        target_data.snapshot_json if target_data else None,
    )
    return MigrationSafetyOut(
        base_snapshot_uuid=against,
        target_snapshot_uuid=schema_snapshot_uuid,
        status="ok",
        analysis=analysis,
    )


@router.get("/{schema_snapshot_uuid}/migration.sql", response_class=PlainTextResponse)
async def export_migration_sql(
    schema_snapshot_uuid: uuid.UUID,
    against: uuid.UUID = Query(
        ..., description="Base snapshot UUID to migrate from"
    ),
    dialect: str = Query("postgresql", pattern="^(postgresql|snowflake)$"),
    direction: str = Query(
        "up",
        pattern="^(up|down)$",
        description="up = base→target (apply), down = target→base (rollback)",
    ),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> str:
    """Generate migration SQL between the base and this (target) snapshot.

    ``direction=up`` (default) moves base → target; ``direction=down`` emits the
    rollback (target → base) — the same generator with the endpoints swapped, so
    up and down are always exact mirrors. Both snapshots are authorized
    independently via project membership; a uniform not-found marker is returned
    if either is missing/unauthorized so existence cannot be enumerated.
    """
    target_snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    base_snap = await _get_authorized_snapshot(session, against, user)
    if target_snap is None or base_snap is None:
        return "-- snapshot not found\n"
    base_data = await session.get(SchemaSnapshotData, against)
    target_data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    base_json = base_data.snapshot_json if base_data else None
    target_json = target_data.snapshot_json if target_data else None
    if direction == "down":
        base_json, target_json = target_json, base_json
    return snapshot_diff_to_migration_sql(
        base_json,
        target_json,
        target_dialect=dialect,
    )


@router.get("/{schema_snapshot_uuid}/export.sql", response_class=PlainTextResponse)
async def export_snapshot_sql(
    schema_snapshot_uuid: uuid.UUID,
    dialect: str = Query("postgresql", pattern="^(postgresql|snowflake)$"),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> str:
    """Export a snapshot as dialect-specific SQL DDL (best-effort)."""
    snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    if snap is None:
        return "-- snapshot not found\n"
    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    if data is None:
        return "-- snapshot data not found\n"
    return snapshot_json_to_sql(data.snapshot_json, target_dialect=dialect)


@router.get("/{schema_snapshot_uuid}/wide-tables", response_model=WideTablesOut)
async def wide_tables(
    schema_snapshot_uuid: uuid.UUID,
    warn_threshold: int = Query(40, ge=1, le=1600),
    info_threshold: int = Query(25, ge=1, le=1600),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> WideTablesOut:
    """Flag wide / denormalized tables by column count (configurable thresholds).

    IDOR-safe (uniform not-found for missing/unauthorized snapshots).
    """
    snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    if snap is None:
        return WideTablesOut(
            schema_snapshot_uuid=schema_snapshot_uuid, status="not_found", report=None
        )
    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    report = detect_wide_tables(
        data.snapshot_json if data else None,
        warn_threshold=warn_threshold,
        info_threshold=info_threshold,
    )
    return WideTablesOut(
        schema_snapshot_uuid=schema_snapshot_uuid, status="ok", report=report
    )


@router.get("/{schema_snapshot_uuid}/stats", response_model=SchemaStatsOut)
async def schema_stats(
    schema_snapshot_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> SchemaStatsOut:
    """Overview statistics for a snapshot (object counts, column & type
    distribution, widest tables, PK/FK/index coverage).

    IDOR-safe (uniform not-found for missing/unauthorized snapshots).
    """
    snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    if snap is None:
        return SchemaStatsOut(
            schema_snapshot_uuid=schema_snapshot_uuid, status="not_found", stats=None
        )
    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    stats = compute_schema_stats(data.snapshot_json if data else None)
    return SchemaStatsOut(
        schema_snapshot_uuid=schema_snapshot_uuid, status="ok", stats=stats
    )


@router.get("/{schema_snapshot_uuid}/fk-cycles", response_model=FkCyclesOut)
async def fk_cycles(
    schema_snapshot_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> FkCyclesOut:
    """Report circular foreign-key dependencies (migration-ordering hazards).

    Multi-table cycles are warnings; self-references are informational.
    IDOR-safe (uniform not-found for missing/unauthorized snapshots).
    """
    snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    if snap is None:
        return FkCyclesOut(
            schema_snapshot_uuid=schema_snapshot_uuid, status="not_found", report=None
        )
    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    report = detect_fk_cycles(data.snapshot_json if data else None)
    return FkCyclesOut(
        schema_snapshot_uuid=schema_snapshot_uuid, status="ok", report=report
    )


@router.get(
    "/{schema_snapshot_uuid}/sensitive-columns", response_model=SensitiveColumnsOut
)
async def sensitive_columns(
    schema_snapshot_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> SensitiveColumnsOut:
    """Compliance-scoping inventory: which columns likely hold PII / card /
    credential data, mapped to the relevant framework (PCI DSS, GDPR/PIPA).

    Detection only -- it does not encrypt, mask, or tokenize anything.
    IDOR-safe (uniform not-found for missing/unauthorized snapshots).
    """
    snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    if snap is None:
        return SensitiveColumnsOut(
            schema_snapshot_uuid=schema_snapshot_uuid, status="not_found", report=None
        )
    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    report = detect_sensitive_columns(data.snapshot_json if data else None)
    return SensitiveColumnsOut(
        schema_snapshot_uuid=schema_snapshot_uuid, status="ok", report=report
    )


@router.get(
    "/{schema_snapshot_uuid}/index-redundancy", response_model=IndexRedundancyOut
)
async def index_redundancy(
    schema_snapshot_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> IndexRedundancyOut:
    """Report duplicate and prefix-shadowed indexes (safe drop candidates).

    Unique indexes are never suggested for dropping (they enforce constraints);
    expression/partial indexes are skipped rather than guessed.
    IDOR-safe (uniform not-found for missing/unauthorized snapshots).
    """
    snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    if snap is None:
        return IndexRedundancyOut(
            schema_snapshot_uuid=schema_snapshot_uuid, status="not_found", report=None
        )
    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    report = detect_index_redundancy(data.snapshot_json if data else None)
    return IndexRedundancyOut(
        schema_snapshot_uuid=schema_snapshot_uuid, status="ok", report=report
    )


@router.get(
    "/{schema_snapshot_uuid}/data-dictionary.md", response_class=PlainTextResponse
)
async def export_data_dictionary(
    schema_snapshot_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> str:
    """Export a snapshot as a Markdown data dictionary, merged with the
    project's table annotations (living documentation)."""
    snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    if snap is None:
        return "-- snapshot not found\n"
    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    if data is None:
        return "-- snapshot data not found\n"
    rows = await session.execute(
        select(TableAnnotation).where(
            TableAnnotation.project_space_uuid == snap.project_space_uuid
        )
    )
    annotations = [
        {
            "schema_name": a.schema_name,
            "relation_name": a.relation_name,
            "body": a.body,
        }
        for a in rows.scalars().all()
    ]
    return snapshot_to_data_dictionary_md(data.snapshot_json, annotations)


@router.get(
    "/{schema_snapshot_uuid}/reversing-spec.md",
    response_class=PlainTextResponse,
)
async def export_snapshot_reversing_spec(
    schema_snapshot_uuid: uuid.UUID,
    mode: str = Query("markdown", pattern="^(markdown|llm-prompt|llm-draft)$"),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> str:
    """Export a snapshot as a DB reversing spec or LLM prompt."""
    snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    if snap is None:
        return "# DB Reversing Specification\n\nSnapshot not found.\n"
    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    if data is None:
        return "# DB Reversing Specification\n\nSnapshot data not found.\n"
    if mode == "llm-draft":
        try:
            return await generate_reversing_llm_draft(data.snapshot_json)
        except LlmConfigurationError as exc:
            raise HTTPException(
                status_code=503, detail="LLM configuration error"
            ) from exc
        except LlmProviderError as exc:
            raise HTTPException(
                status_code=502, detail="LLM provider request failed"
            ) from exc
    return generate_reversing_spec(data.snapshot_json, mode=mode)


@router.get(
    "/{schema_snapshot_uuid}/index-design.md",
    response_class=PlainTextResponse,
)
async def export_snapshot_index_design(
    schema_snapshot_uuid: uuid.UUID,
    mode: str = Query("markdown", pattern="^(markdown|llm-prompt|llm-draft)$"),
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> str:
    """Export table/index design guidance or an LLM prompt."""
    snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    if snap is None:
        return "# ERD Index Design\n\nSnapshot not found.\n"
    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    if data is None:
        return "# ERD Index Design\n\nSnapshot data not found.\n"
    if mode == "llm-draft":
        try:
            return await generate_index_design_llm_draft(data.snapshot_json)
        except LlmConfigurationError as exc:
            raise HTTPException(
                status_code=503, detail="LLM configuration error"
            ) from exc
        except LlmProviderError as exc:
            raise HTTPException(
                status_code=502, detail="LLM provider request failed"
            ) from exc
    return generate_index_design_spec(data.snapshot_json, mode=mode)


@router.get("/by-project/{project_space_uuid}", response_model=list[SnapshotOut])
async def list_snapshots(
    project_space_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> list[SnapshotOut]:
    """List snapshots for a project."""
    await require_project_member(session, project_space_uuid, user.user_account_uuid)
    rows = await session.execute(
        select(SchemaSnapshot)
        .where(SchemaSnapshot.project_space_uuid == project_space_uuid)
        .order_by(SchemaSnapshot.created_at.desc())
    )
    snaps = rows.scalars().all()
    return [
        SnapshotOut(
            schema_snapshot_uuid=s.schema_snapshot_uuid,
            status=s.status,
            schema_filter=s.schema_filter,
        )
        for s in snaps
    ]


@router.get("/{schema_snapshot_uuid}/naming-lint", response_model=NamingLintOut)
async def naming_lint(
    schema_snapshot_uuid: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_read_session),
) -> NamingLintOut:
    """Lint identifier names: reserved words and quoting-required names (breaking),
    discouraged keywords, and case inconsistency vs the schema's own dominant style.

    IDOR-safe (uniform not-found for missing/unauthorized snapshots).
    """
    snap = await _get_authorized_snapshot(session, schema_snapshot_uuid, user)
    if snap is None:
        return NamingLintOut(
            schema_snapshot_uuid=schema_snapshot_uuid, status="not_found", report=None
        )
    data = await session.get(SchemaSnapshotData, schema_snapshot_uuid)
    report = lint_naming(data.snapshot_json if data else None)
    return NamingLintOut(
        schema_snapshot_uuid=schema_snapshot_uuid, status="ok", report=report
    )
