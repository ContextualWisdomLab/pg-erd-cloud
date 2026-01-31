"""auth + share links + foreign keys

Revision ID: 0002_auth_share
Revises: 0001_init
Create Date: 2026-01-31

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_auth_share"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add FK constraints (MVP: best-effort for fresh DB)
    op.create_foreign_key(
        "fk_project_space__created_by_user",
        "project_space",
        "user_account",
        ["created_by_user_uuid"],
        ["user_account_uuid"],
    )
    op.create_foreign_key(
        "fk_project_member__project_space",
        "project_member",
        "project_space",
        ["project_space_uuid"],
        ["project_space_uuid"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_project_member__user_account",
        "project_member",
        "user_account",
        ["user_account_uuid"],
        ["user_account_uuid"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_db_connection__project_space",
        "db_connection",
        "project_space",
        ["project_space_uuid"],
        ["project_space_uuid"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_schema_snapshot__project_space",
        "schema_snapshot",
        "project_space",
        ["project_space_uuid"],
        ["project_space_uuid"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_schema_snapshot__db_connection",
        "schema_snapshot",
        "db_connection",
        ["db_connection_uuid"],
        ["db_connection_uuid"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_schema_snapshot_data__schema_snapshot",
        "schema_snapshot_data",
        "schema_snapshot",
        ["schema_snapshot_uuid"],
        ["schema_snapshot_uuid"],
        ondelete="CASCADE",
    )

    # Share links
    op.create_table(
        "share_link",
        sa.Column("share_link_uuid", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("project_space_uuid", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_uuid", sa.Uuid(), nullable=False),
        sa.Column("permission_kind", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_share_link__project_space_uuid",
        "share_link",
        ["project_space_uuid"],
    )
    op.create_foreign_key(
        "fk_share_link__project_space",
        "share_link",
        "project_space",
        ["project_space_uuid"],
        ["project_space_uuid"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_share_link__created_by_user",
        "share_link",
        "user_account",
        ["created_by_user_uuid"],
        ["user_account_uuid"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_share_link__created_by_user", "share_link", type_="foreignkey"
    )
    op.drop_constraint("fk_share_link__project_space", "share_link", type_="foreignkey")
    op.drop_index("ix_share_link__project_space_uuid", table_name="share_link")
    op.drop_table("share_link")

    op.drop_constraint(
        "fk_schema_snapshot_data__schema_snapshot",
        "schema_snapshot_data",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_schema_snapshot__db_connection", "schema_snapshot", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_schema_snapshot__project_space", "schema_snapshot", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_db_connection__project_space", "db_connection", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_project_member__user_account", "project_member", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_project_member__project_space", "project_member", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_project_space__created_by_user", "project_space", type_="foreignkey"
    )
