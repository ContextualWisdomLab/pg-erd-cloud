"""lease-bound migration worker attempts

Revision ID: 0011_migration_run_attempt
Revises: 0010_migration_run
Create Date: 2026-08-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011_migration_run_attempt"
down_revision = "0010_migration_run"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create durable hashed worker-attempt ownership history."""

    op.create_table(
        "migration_run_attempt",
        sa.Column(
            "migration_run_attempt_uuid",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "migration_run_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("migration_run.migration_run_uuid", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("acquired_state_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("worker_identity_hash", sa.Text(), nullable=False),
        sa.Column("signal_lease_token_hash", sa.Text(), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "migration_run_uuid",
            "attempt_number",
            name="uq_migration_run_attempt__run_number",
        ),
        sa.CheckConstraint(
            "attempt_number >= 1",
            name="ck_migration_run_attempt__attempt_number",
        ),
        sa.CheckConstraint(
            "acquired_state_version >= 1",
            name="ck_migration_run_attempt__acquired_state_version",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'completed', 'abandoned')",
            name="ck_migration_run_attempt__status",
        ),
        sa.CheckConstraint(
            "worker_identity_hash ~ '^[0-9a-f]{64}$'",
            name="ck_migration_run_attempt__worker_identity_hash",
        ),
        sa.CheckConstraint(
            "signal_lease_token_hash ~ '^[0-9a-f]{64}$'",
            name="ck_migration_run_attempt__signal_lease_token_hash",
        ),
        sa.CheckConstraint(
            "last_heartbeat_at >= acquired_at AND "
            "lease_expires_at > acquired_at AND "
            "((status = 'active' AND finished_at IS NULL) OR "
            "(status IN ('completed', 'abandoned') AND finished_at IS NOT NULL "
            "AND finished_at >= last_heartbeat_at))",
            name="ck_migration_run_attempt__timestamps",
        ),
    )
    op.create_index(
        "ix_migration_run_attempt__active_run",
        "migration_run_attempt",
        ["migration_run_uuid"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_migration_run_attempt__lease_expiry",
        "migration_run_attempt",
        ["status", "lease_expires_at"],
    )


def downgrade() -> None:
    """Remove worker-attempt history."""

    op.drop_index(
        "ix_migration_run_attempt__lease_expiry",
        table_name="migration_run_attempt",
    )
    op.drop_index(
        "ix_migration_run_attempt__active_run",
        table_name="migration_run_attempt",
    )
    op.drop_table("migration_run_attempt")
