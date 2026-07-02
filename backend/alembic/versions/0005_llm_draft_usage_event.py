"""llm draft usage billing attribution

Revision ID: 0005_llm_draft_usage_event
Revises: 0004_billing_event
Create Date: 2026-07-03

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_llm_draft_usage_event"
down_revision = "0004_billing_event"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_draft_usage_event",
        sa.Column(
            "llm_draft_usage_event_uuid",
            sa.Uuid(),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("surface", sa.Text(), nullable=False),
        sa.Column("artifact", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("user_account_uuid", sa.Uuid(), nullable=True),
        sa.Column("project_space_uuid", sa.Uuid(), nullable=True),
        sa.Column("schema_snapshot_uuid", sa.Uuid(), nullable=True),
        sa.Column("share_link_uuid", sa.Uuid(), nullable=True),
        sa.Column("input_chars", sa.Integer(), nullable=False),
        sa.Column("output_chars", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_account_uuid"],
            ["user_account.user_account_uuid"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_space_uuid"],
            ["project_space.project_space_uuid"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["schema_snapshot_uuid"],
            ["schema_snapshot.schema_snapshot_uuid"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["share_link_uuid"],
            ["share_link.share_link_uuid"],
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_llm_draft_usage_event__account_month",
        "llm_draft_usage_event",
        ["user_account_uuid", "occurred_at"],
    )
    op.create_index(
        "ix_llm_draft_usage_event__project_month",
        "llm_draft_usage_event",
        ["project_space_uuid", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_llm_draft_usage_event__project_month",
        table_name="llm_draft_usage_event",
    )
    op.drop_index(
        "ix_llm_draft_usage_event__account_month",
        table_name="llm_draft_usage_event",
    )
    op.drop_table("llm_draft_usage_event")
