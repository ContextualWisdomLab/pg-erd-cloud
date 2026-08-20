"""Add a partial access path for the due job queue working set.

Revision ID: 0009_hot_queue_claim_index
Revises: 0008_reconcile_model_metadata
Create Date: 2026-08-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_hot_queue_claim_index"
down_revision = "0008_reconcile_model_metadata"
branch_labels = None
depends_on = None

_INDEX_NAME = "ix_job_queue__queued_run_after_uuid"


def upgrade() -> None:
    """Index only queued jobs so terminal history does not enlarge the hot path."""
    op.create_index(
        _INDEX_NAME,
        "job_queue",
        ["run_after", "job_queue_uuid"],
        postgresql_where=sa.text("status = 'queued'"),
    )


def downgrade() -> None:
    """Remove the queue working-set index without touching job records."""
    op.drop_index(_INDEX_NAME, table_name="job_queue")
