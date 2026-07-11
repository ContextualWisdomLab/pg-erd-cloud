"""table_annotation: per-project notes attached to tables by name

Revision ID: 0006_table_annotation
Revises: 0005_diagram_view
Create Date: 2026-07-05

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_table_annotation"
down_revision = "0005_diagram_view"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "table_annotation",
        sa.Column("table_annotation_uuid", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("project_space_uuid", sa.Uuid(), nullable=False),
        sa.Column("schema_name", sa.Text(), nullable=False),
        sa.Column("relation_name", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_space_uuid"],
            ["project_space.project_space_uuid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("table_annotation_uuid"),
        sa.UniqueConstraint(
            "project_space_uuid",
            "schema_name",
            "relation_name",
            name="uq_table_annotation__project_table",
        ),
    )
    op.create_index(
        "ix_table_annotation__project_space_uuid",
        "table_annotation",
        ["project_space_uuid"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_table_annotation__project_space_uuid", table_name="table_annotation"
    )
    op.drop_table("table_annotation")
