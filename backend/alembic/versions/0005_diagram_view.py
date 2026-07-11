"""diagram_view: saved ERD canvas views

Revision ID: 0005_diagram_view
Revises: 0004_merge_heads
Create Date: 2026-07-05

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_diagram_view"
down_revision = "0004_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "diagram_view",
        sa.Column("diagram_view_uuid", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("project_space_uuid", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("layout_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_space_uuid"],
            ["project_space.project_space_uuid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("diagram_view_uuid"),
    )
    op.create_index(
        "ix_diagram_view__project_space_uuid",
        "diagram_view",
        ["project_space_uuid"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_diagram_view__project_space_uuid", table_name="diagram_view"
    )
    op.drop_table("diagram_view")
