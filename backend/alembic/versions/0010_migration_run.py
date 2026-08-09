"""durable migration runs and append-only events

Revision ID: 0010_migration_run
Revises: 0009_migration_plan
Create Date: 2026-08-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_migration_run"
down_revision = "0009_migration_plan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create durable run identity and append-only transition evidence."""

    op.create_table(
        "migration_run",
        sa.Column(
            "migration_run_uuid", postgresql.UUID(as_uuid=True), primary_key=True
        ),
        sa.Column(
            "project_space_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("project_space.project_space_uuid", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "migration_plan_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("migration_plan.migration_plan_uuid", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("run_kind", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key_hash", sa.Text(), nullable=False),
        sa.Column("plan_digest", sa.Text(), nullable=False),
        sa.Column(
            "requested_by_user_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_account.user_account_uuid"),
            nullable=False,
        ),
        sa.Column("cancellation_requested", sa.Boolean(), nullable=False),
        sa.Column("observed_base_digest", sa.Text(), nullable=True),
        sa.Column("evidence_json", postgresql.JSONB(), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "project_space_uuid",
            "migration_plan_uuid",
            "run_kind",
            "idempotency_key_hash",
            name="uq_migration_run__idempotent_action",
        ),
        sa.CheckConstraint(
            "run_kind IN ('dry_run', 'apply')",
            name="ck_migration_run__run_kind",
        ),
        sa.CheckConstraint(
            "state IN ('queued', 'sandbox_running', 'live_preflight_running', "
            "'passed', 'drifted', 'failed', 'applying', 'reconciling', "
            "'verifying', 'verified', 'drifted_no_apply', 'not_applied', "
            "'verification_failed', 'failed_rolled_back', "
            "'applied_with_drift', 'outcome_unknown')",
            name="ck_migration_run__state",
        ),
        sa.CheckConstraint(
            "state_version >= 1", name="ck_migration_run__state_version"
        ),
    )
    op.create_index(
        "ix_migration_run__project_space_uuid",
        "migration_run",
        ["project_space_uuid"],
    )
    op.create_index(
        "ix_migration_run__migration_plan_uuid",
        "migration_run",
        ["migration_plan_uuid"],
    )
    op.create_index(
        "ix_migration_run__project_state",
        "migration_run",
        ["project_space_uuid", "state"],
    )

    op.create_table(
        "migration_run_event",
        sa.Column(
            "migration_run_event_uuid",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "migration_run_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("migration_run.migration_run_uuid", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("state_before", sa.Text(), nullable=True),
        sa.Column("state_after", sa.Text(), nullable=False),
        sa.Column("evidence_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "actor_user_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_account.user_account_uuid"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "migration_run_uuid",
            "sequence_number",
            name="uq_migration_run_event__run_sequence",
        ),
        sa.CheckConstraint(
            "sequence_number >= 1",
            name="ck_migration_run_event__sequence_number",
        ),
    )
    op.create_index(
        "ix_migration_run_event__migration_run_uuid",
        "migration_run_event",
        ["migration_run_uuid"],
    )


def downgrade() -> None:
    """Remove run evidence before its parent run identity."""

    op.drop_index(
        "ix_migration_run_event__migration_run_uuid",
        table_name="migration_run_event",
    )
    op.drop_table("migration_run_event")
    op.drop_index("ix_migration_run__project_state", table_name="migration_run")
    op.drop_index(
        "ix_migration_run__migration_plan_uuid", table_name="migration_run"
    )
    op.drop_index(
        "ix_migration_run__project_space_uuid", table_name="migration_run"
    )
    op.drop_table("migration_run")
