from __future__ import annotations

from app.models import JobQueue


def test_job_queue_has_a_partial_due_working_set_index() -> None:
    """Keep the due queued-job access path bounded as terminal history grows."""
    index = next(
        index
        for index in JobQueue.__table__.indexes
        if index.name == "ix_job_queue__queued_run_after_uuid"
    )

    assert [column.name for column in index.columns] == [
        "run_after",
        "job_queue_uuid",
    ]
    assert str(index.dialect_options["postgresql"]["where"]) == "status = 'queued'"
