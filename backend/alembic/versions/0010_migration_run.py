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
        sa.Column("request_digest", sa.Text(), nullable=False),
        sa.Column("latest_event_digest", sa.Text(), nullable=False),
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
            "(run_kind = 'dry_run' AND state IN ('queued', 'sandbox_running', "
            "'live_preflight_running', 'passed', 'drifted', 'failed')) OR "
            "(run_kind = 'apply' AND state IN ('queued', 'applying', "
            "'reconciling', 'verifying', 'verified', 'drifted_no_apply', "
            "'not_applied', 'verification_failed', 'failed_rolled_back', "
            "'applied_with_drift', 'outcome_unknown'))",
            name="ck_migration_run__kind_state",
        ),
        sa.CheckConstraint(
            "state_version >= 1", name="ck_migration_run__state_version"
        ),
        sa.CheckConstraint(
            "latest_event_digest ~ '^[0-9a-f]{64}$'",
            name="ck_migration_run__latest_event_digest",
        ),
        sa.CheckConstraint(
            "idempotency_key_hash ~ '^[0-9a-f]{64}$'",
            name="ck_migration_run__idempotency_key_hash",
        ),
        sa.CheckConstraint(
            "plan_digest ~ '^[0-9a-f]{64}$'",
            name="ck_migration_run__plan_digest",
        ),
        sa.CheckConstraint(
            "request_digest ~ '^[0-9a-f]{64}$'",
            name="ck_migration_run__request_digest",
        ),
        sa.CheckConstraint(
            "observed_base_digest IS NULL OR "
            "observed_base_digest ~ '^[0-9a-f]{64}$'",
            name="ck_migration_run__observed_base_digest",
        ),
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
        "migration_run_dispatch",
        sa.Column(
            "migration_run_dispatch_uuid",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "migration_run_uuid",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("migration_run.migration_run_uuid", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dispatch_kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "migration_run_uuid",
            name="uq_migration_run_dispatch__migration_run_uuid",
        ),
        sa.CheckConstraint(
            "dispatch_kind = 'isolated_dry_run'",
            name="ck_migration_run_dispatch__dispatch_kind",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'published')",
            name="ck_migration_run_dispatch__status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_migration_run_dispatch__attempt_count",
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND published_at IS NULL) OR "
            "(status = 'published' AND published_at IS NOT NULL)",
            name="ck_migration_run_dispatch__published_at",
        ),
    )
    op.create_index(
        "ix_migration_run_dispatch__status_not_before",
        "migration_run_dispatch",
        ["status", "not_before"],
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
        sa.Column("previous_event_digest", sa.Text(), nullable=True),
        sa.Column("event_digest", sa.Text(), nullable=False),
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
        sa.CheckConstraint(
            "(sequence_number = 1 AND previous_event_digest IS NULL) OR "
            "(sequence_number > 1 AND previous_event_digest IS NOT NULL)",
            name="ck_migration_run_event__previous_digest",
        ),
        sa.CheckConstraint(
            "previous_event_digest IS NULL OR "
            "previous_event_digest ~ '^[0-9a-f]{64}$'",
            name="ck_migration_run_event__previous_digest_format",
        ),
        sa.CheckConstraint(
            "event_digest ~ '^[0-9a-f]{64}$'",
            name="ck_migration_run_event__event_digest",
        ),
        sa.CheckConstraint(
            "event_type ~ '^[a-z][a-z0-9_]{0,63}$'",
            name="ck_migration_run_event__event_type",
        ),
        sa.CheckConstraint(
            "state_before IS NULL OR state_before IN ('queued', 'sandbox_running', 'live_preflight_running', 'passed', 'drifted', 'failed', 'applying', 'reconciling', 'verifying', 'verified', 'drifted_no_apply', 'not_applied', 'verification_failed', 'failed_rolled_back', 'applied_with_drift', 'outcome_unknown')",
            name="ck_migration_run_event__state_before",
        ),
        sa.CheckConstraint(
            "state_after IN ('queued', 'sandbox_running', 'live_preflight_running', 'passed', 'drifted', 'failed', 'applying', 'reconciling', 'verifying', 'verified', 'drifted_no_apply', 'not_applied', 'verification_failed', 'failed_rolled_back', 'applied_with_drift', 'outcome_unknown')",
            name="ck_migration_run_event__state_after",
        ),
    )


def downgrade() -> None:
    """Remove run evidence before its parent run identity."""

    op.drop_table("migration_run_event")
    op.drop_index(
        "ix_migration_run_dispatch__status_not_before",
        table_name="migration_run_dispatch",
    )
    op.drop_table("migration_run_dispatch")
    op.drop_index("ix_migration_run__project_state", table_name="migration_run")
    op.drop_index(
        "ix_migration_run__migration_plan_uuid", table_name="migration_run"
    )
    op.drop_table("migration_run")
