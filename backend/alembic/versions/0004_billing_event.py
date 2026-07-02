"""billing event reconciliation

Revision ID: 0004_billing_event
Revises: 0003, 0003_validate_project_space_fk
Create Date: 2026-07-02

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_billing_event"
down_revision = ("0003", "0003_validate_project_space_fk")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_event",
        sa.Column("billing_event_uuid", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_event_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("target_plan", sa.Text(), nullable=True),
        sa.Column("event_status", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "provider",
            "provider_event_id",
            name="uq_billing_event__provider_event_id",
        ),
    )
    op.create_index(
        "ix_billing_event__subject_received_at",
        "billing_event",
        ["subject", "received_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_billing_event__subject_received_at",
        table_name="billing_event",
    )
    op.drop_table("billing_event")
