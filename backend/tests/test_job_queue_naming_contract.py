from __future__ import annotations

from pathlib import Path

from app.models import JobQueue


def test_job_queue_owns_semantic_status_column() -> None:
    """Persist queue state under the bounded-context ``job_status`` name."""

    assert "job_status" in JobQueue.__table__.columns
    assert "status" not in JobQueue.__table__.columns

    job_queue_index = next(
        queue_index
        for queue_index in JobQueue.__table__.indexes
        if queue_index.name == "ix_job_queue__job_status_run_after"
    )
    assert [queue_column.name for queue_column in job_queue_index.columns] == [
        "job_status",
        "run_after",
    ]


def test_worker_claim_sql_uses_semantic_job_status() -> None:
    """Keep every raw queue claim aligned with the physical ``job_status`` column."""

    worker_source_path = (
        Path(__file__).resolve().parents[1] / "app" / "jobs" / "worker.py"
    )
    worker_source = worker_source_path.read_text(encoding="utf-8")

    assert "job.status" not in worker_source
    assert "WHERE status = 'queued'" not in worker_source
    assert "AND status = 'queued'" not in worker_source
    assert "job.job_status" in worker_source
    assert "job_status = 'queued'" in worker_source


def test_job_status_migration_preserves_index_without_rebuild() -> None:
    """Require a reversible metadata rename for the persisted queue contract."""

    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0008_job_queue_status_name.py"
    )
    migration_source = migration_path.read_text(encoding="utf-8")

    assert 'new_column_name="job_status"' in migration_source
    assert (
        "ALTER INDEX ix_job_queue__status_run_after "
        "RENAME TO ix_job_queue__job_status_run_after"
    ) in migration_source
    assert 'new_column_name="status"' in migration_source
    assert (
        "ALTER INDEX ix_job_queue__job_status_run_after "
        "RENAME TO ix_job_queue__status_run_after"
    ) in migration_source
