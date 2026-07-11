"""api_key table for programmatic access

Revision ID: 0007_api_key
Revises: 0006_table_annotation
Create Date: 2026-07-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0007_api_key"
down_revision = "0006_table_annotation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_key",
        sa.Column("api_key_uuid", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_account_uuid",
            UUID(as_uuid=True),
            sa.ForeignKey("user_account.user_account_uuid", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key_name", sa.Text(), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("key_prefix", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_api_key__user", "api_key", ["user_account_uuid"])
    op.create_index("ix_api_key__hash", "api_key", ["key_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_api_key__hash", table_name="api_key")
    op.drop_index("ix_api_key__user", table_name="api_key")
    op.drop_table("api_key")
