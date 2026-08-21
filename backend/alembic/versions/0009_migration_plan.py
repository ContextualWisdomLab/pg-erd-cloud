"""immutable migration plans

Revision ID: 0009_migration_plan
Revises: 0008_schema_model_revision
Create Date: 2026-08-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_migration_plan"
down_revision = "0008_schema_model_revision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "migration_plan",
        sa.Column("migration_plan_uuid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_space_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_space.project_space_uuid", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "schema_model_revision_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "schema_model_revision.schema_model_revision_uuid",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "db_connection_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("db_connection.db_connection_uuid", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "base_schema_snapshot_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schema_snapshot.schema_snapshot_uuid", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("compiler_version", sa.Text(), nullable=False),
        sa.Column("base_digest", sa.Text(), nullable=False),
        sa.Column("target_digest", sa.Text(), nullable=False),
        sa.Column("statement_digest", sa.Text(), nullable=False),
        sa.Column("plan_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_by_user_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_account.user_account_uuid"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "schema_model_revision_uuid",
            "db_connection_uuid",
            "base_schema_snapshot_uuid",
            "statement_digest",
            name="uq_migration_plan__immutable_identity",
        ),
    )
    op.create_index(
        "ix_migration_plan__project_space_uuid",
        "migration_plan",
        ["project_space_uuid"],
    )
    op.create_index(
        "ix_migration_plan__schema_model_revision_uuid",
        "migration_plan",
        ["schema_model_revision_uuid"],
    )
    op.create_index(
        "ix_migration_plan__expires_at",
        "migration_plan",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_migration_plan__expires_at", table_name="migration_plan")
    op.drop_index(
        "ix_migration_plan__schema_model_revision_uuid", table_name="migration_plan"
    )
    op.drop_index(
        "ix_migration_plan__project_space_uuid", table_name="migration_plan"
    )
    op.drop_table("migration_plan")
