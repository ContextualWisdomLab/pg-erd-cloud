"""init

Revision ID: 0001_init
Revises:
Create Date: 2026-01-31

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_account",
        sa.Column("user_account_uuid", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("oidc_subject", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "project_space",
        sa.Column("project_space_uuid", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("project_name", sa.Text(), nullable=False),
        sa.Column("created_by_user_uuid", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_project_space__created_by_user_uuid",
        "project_space",
        ["created_by_user_uuid"],
    )

    op.create_table(
        "project_member",
        sa.Column("project_space_uuid", sa.Uuid(), nullable=False),
        sa.Column("user_account_uuid", sa.Uuid(), nullable=False),
        sa.Column("project_role", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("project_space_uuid", "user_account_uuid"),
    )
    op.create_index(
        "ix_project_member__user_account_uuid",
        "project_member",
        ["user_account_uuid"],
    )

    op.create_table(
        "db_connection",
        sa.Column("db_connection_uuid", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("project_space_uuid", sa.Uuid(), nullable=False),
        sa.Column("conn_name", sa.Text(), nullable=False),
        sa.Column("dsn_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("dsn_nonce", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_db_connection__project_space_uuid",
        "db_connection",
        ["project_space_uuid"],
    )

    op.create_table(
        "schema_snapshot",
        sa.Column("schema_snapshot_uuid", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("project_space_uuid", sa.Uuid(), nullable=False),
        sa.Column("db_connection_uuid", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("schema_filter", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_schema_snapshot__project_space_uuid",
        "schema_snapshot",
        ["project_space_uuid"],
    )

    op.create_table(
        "schema_snapshot_data",
        sa.Column("schema_snapshot_uuid", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "job_queue",
        sa.Column("job_queue_uuid", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_job_queue__status_run_after", "job_queue", ["status", "run_after"]
    )


def downgrade() -> None:
    op.drop_index("ix_job_queue__status_run_after", table_name="job_queue")
    op.drop_table("job_queue")

    op.drop_table("schema_snapshot_data")
    op.drop_index(
        "ix_schema_snapshot__project_space_uuid", table_name="schema_snapshot"
    )
    op.drop_table("schema_snapshot")

    op.drop_index("ix_db_connection__project_space_uuid", table_name="db_connection")
    op.drop_table("db_connection")

    op.drop_index("ix_project_member__user_account_uuid", table_name="project_member")
    op.drop_table("project_member")

    op.drop_index("ix_project_space__created_by_user_uuid", table_name="project_space")
    op.drop_table("project_space")

    op.drop_table("user_account")
