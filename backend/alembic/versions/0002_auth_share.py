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


_MIGRATED_OIDC_SUBJECT_PREFIX = "migrated:0002_auth_share:"
_MIGRATED_DISPLAY_NAME_PREFIX = "migrated-0002_auth_share-"


def upgrade() -> None:
    # Backfill: ensure any existing project_space.created_by_user_uuid values exist in user_account
    # before adding FK constraints. Previous versions could have inserted random UUIDs.
    conn = op.get_bind()
    conn.execute(
        sa.text("""
            INSERT INTO user_account (user_account_uuid, oidc_subject, display_name, created_at)
            SELECT DISTINCT
              p.created_by_user_uuid,
              :oidc_prefix || p.created_by_user_uuid::text,
              :display_prefix || p.created_by_user_uuid::text,
              now()
            FROM project_space p
            LEFT JOIN user_account u ON u.user_account_uuid = p.created_by_user_uuid
            WHERE p.created_by_user_uuid IS NOT NULL AND u.user_account_uuid IS NULL
            ON CONFLICT DO NOTHING;
            """),
        {
            "oidc_prefix": _MIGRATED_OIDC_SUBJECT_PREFIX,
            "display_prefix": _MIGRATED_DISPLAY_NAME_PREFIX,
        },
    )

    # Add FK constraints (MVP: best-effort for fresh DB)
    op.create_foreign_key(
        "fk_project_space__created_by_user",
        "project_space",
        "user_account",
        ["created_by_user_uuid"],
        ["user_account_uuid"],
        postgresql_not_valid=True,
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
        "fk_schema_snapshot__db_connection",
        "schema_snapshot",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_schema_snapshot__project_space",
        "schema_snapshot",
        type_="foreignkey",
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

    # Remove backfilled user_account rows created during upgrade.
    conn = op.get_bind()
    conn.execute(
        sa.text("""
            DELETE FROM user_account
            WHERE oidc_subject LIKE :oidc_prefix_like;
            """),
        {"oidc_prefix_like": f"{_MIGRATED_OIDC_SUBJECT_PREFIX}%"},
    )
