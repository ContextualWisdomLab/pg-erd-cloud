"""versioned editable schema models

Revision ID: 0008_schema_model_revision
Revises: 0007_api_key
Create Date: 2026-08-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_schema_model_revision"
down_revision = "0007_api_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schema_model",
        sa.Column("schema_model_uuid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_space_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_space.project_space_uuid", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("current_revision_number", sa.Integer(), nullable=False),
        sa.Column(
            "created_by_user_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_account.user_account_uuid"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "project_space_uuid", "model_name", name="uq_schema_model__project_name"
        ),
    )
    op.create_index(
        "ix_schema_model__project_space_uuid", "schema_model", ["project_space_uuid"]
    )
    op.create_table(
        "schema_model_revision",
        sa.Column(
            "schema_model_revision_uuid",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "schema_model_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schema_model.schema_model_uuid", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("revision_digest", sa.Text(), nullable=False),
        sa.Column("model_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "base_schema_snapshot_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schema_snapshot.schema_snapshot_uuid", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_by_user_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_account.user_account_uuid"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "schema_model_uuid",
            "revision_number",
            name="uq_schema_model_revision__model_number",
        ),
    )
    op.create_index(
        "ix_schema_model_revision__schema_model_uuid",
        "schema_model_revision",
        ["schema_model_uuid"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_schema_model_revision__schema_model_uuid",
        table_name="schema_model_revision",
    )
    op.drop_table("schema_model_revision")
    op.drop_index("ix_schema_model__project_space_uuid", table_name="schema_model")
    op.drop_table("schema_model")
