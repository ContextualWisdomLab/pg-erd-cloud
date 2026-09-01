"""qualify the persisted job queue status name

Revision ID: 0008_job_queue_status_name
Revises: 0007_api_key
Create Date: 2026-09-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_job_queue_status_name"
down_revision = "0007_api_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rename queue status metadata without rebuilding the claim-path index."""

    op.alter_column(
        "job_queue",
        "status",
        new_column_name="job_status",
        existing_type=sa.Text(),
        existing_nullable=False,
    )
    op.execute(
        "ALTER INDEX ix_job_queue__status_run_after "
        "RENAME TO ix_job_queue__job_status_run_after"
    )


def downgrade() -> None:
    """Restore the historical queue status and index names."""

    op.alter_column(
        "job_queue",
        "job_status",
        new_column_name="status",
        existing_type=sa.Text(),
        existing_nullable=False,
    )
    op.execute(
        "ALTER INDEX ix_job_queue__job_status_run_after "
        "RENAME TO ix_job_queue__status_run_after"
    )
